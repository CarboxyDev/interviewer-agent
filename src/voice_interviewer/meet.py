from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections import defaultdict, deque
from contextlib import suppress
from pathlib import Path
from typing import Literal

from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    async_playwright,
)

from voice_interviewer.domain import FailureCode, JoinOutcome
from voice_interviewer.errors import InterviewerError

SECURITY_TEXT = re.compile(
    r"captcha|unusual traffic|verify (that )?you are human|sign in to continue|couldn't let you in",
    re.IGNORECASE,
)
DENIAL_TEXT = re.compile(
    r"you can't join|not allowed to join|denied (?:your )?request|"
    r"request to join was denied|weren't allowed into this meeting|"
    r"no one responded to your request|removed from the meeting",
    re.IGNORECASE,
)
PARTICIPANT_COUNT = re.compile(r"\b(\d+)\s+(?:participant|people|person)", re.IGNORECASE)
GUEST_NAME_INPUT = (
    'input[placeholder*="name" i], input[aria-label*="name" i], input[name*="name" i]'
)
JOIN_BUTTON_TEXT = re.compile(r"join now|rejoin", re.IGNORECASE)
ASK_TO_JOIN_TEXT = re.compile(r"ask to join", re.IGNORECASE)
LEAVE_CALL_TEXT = re.compile(r"leave call", re.IGNORECASE)
DIRECT_JOIN_TIMEOUT_SECONDS = 20
BROWSER_SINGLETON_FILES = ("SingletonCookie", "SingletonLock", "SingletonSocket")


def remove_browser_singleton_locks(profile_dir: Path) -> None:
    for name in BROWSER_SINGLETON_FILES:
        lock = profile_dir / name
        if lock.is_symlink() or lock.is_file():
            lock.unlink(missing_ok=True)


def chromium_cdp_args(*, profile_dir: Path, port: int, headless: bool) -> list[str]:
    args = [
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--autoplay-policy=no-user-gesture-required",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
    ]
    if headless:
        args.append("--headless=new")
    return [*args, "about:blank"]


def participant_count_from_labels(labels: list[str]) -> int | None:
    counts = [int(match.group(1)) for label in labels if (match := PARTICIPANT_COUNT.search(label))]
    return max(counts) if counts else None


def compact_page_text(text: str, limit: int = 400) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def guard_page_failure(body: str) -> tuple[FailureCode, str] | None:
    security_match = SECURITY_TEXT.search(body)
    if security_match:
        matched_text = compact_page_text(security_match.group(0), limit=120)
        return (
            FailureCode.GOOGLE_SECURITY_INTERVENTION,
            "Google requested an account or security check. "
            f"The bot will not bypass it. Matched guard text: {matched_text}",
        )

    denial_match = DENIAL_TEXT.search(body)
    if denial_match:
        matched_text = compact_page_text(denial_match.group(0), limit=120)
        return (
            FailureCode.MEETING_ACCESS_DENIED,
            f"Google Meet denied or removed the guest. Matched guard text: {matched_text}",
        )

    return None


class MeetingAttemptLimiter:
    def __init__(
        self,
        *,
        cooldown_seconds: int = 300,
        hourly_limit: int = 3,
        state_path: Path | None = None,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.hourly_limit = hourly_limit
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self.state_path = state_path
        self._load()

    def check_and_record(self, meeting_url: str, now: float | None = None) -> None:
        current = time.time() if now is None else now
        self._prune(current)
        meeting_key = hashlib.sha256(meeting_url.encode("utf-8")).hexdigest()
        attempts = self._attempts[meeting_key]
        if (
            self.cooldown_seconds > 0
            and attempts
            and current - attempts[-1] < self.cooldown_seconds
        ):
            raise InterviewerError(
                FailureCode.MEETING_ACCESS_DENIED,
                "Meet join cooldown is active; no automated retry was attempted",
            )
        total_attempts = sum(len(recent) for recent in self._attempts.values())
        if self.hourly_limit > 0 and total_attempts >= self.hourly_limit:
            raise InterviewerError(
                FailureCode.MEETING_ACCESS_DENIED,
                "Meet join limit reached for this browser profile; "
                "no automated retry was attempted",
            )
        attempts.append(current)
        self._save()

    def _prune(self, current: float) -> None:
        for meeting_url in list(self._attempts):
            attempts = self._attempts[meeting_url]
            while attempts and current - attempts[0] >= 3600:
                attempts.popleft()
            if not attempts:
                del self._attempts[meeting_url]

    def _load(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Meet attempt ledger must be a JSON object")
        for meeting_url, timestamps in payload.items():
            if not isinstance(meeting_url, str) or not isinstance(timestamps, list):
                raise ValueError("Meet attempt ledger contains an invalid entry")
            if not all(isinstance(timestamp, int | float) for timestamp in timestamps):
                raise ValueError("Meet attempt ledger contains an invalid timestamp")
            self._attempts[meeting_url].extend(float(timestamp) for timestamp in timestamps)

    def _save(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        payload = {url: list(attempts) for url, attempts in self._attempts.items()}
        temporary_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temporary_path.replace(self.state_path)
        self.state_path.chmod(0o600)


class PlaywrightMeetTransport:
    def __init__(
        self,
        *,
        headless: bool,
        profile_dir: Path,
        connection_mode: Literal["cdp", "playwright"] = "cdp",
        cdp_port: int = 9222,
        browser_channel: str | None = None,
        browser_executable_path: Path | None = None,
        limiter: MeetingAttemptLimiter | None = None,
    ) -> None:
        self.headless = headless
        self.profile_dir = profile_dir
        self.connection_mode = connection_mode
        self.cdp_port = cdp_port
        self.browser_channel = browser_channel
        self.browser_executable_path = browser_executable_path
        self.limiter = limiter or MeetingAttemptLimiter(
            state_path=self.profile_dir.parent / "meet-attempts.json"
        )
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._browser_process: asyncio.subprocess.Process | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def join(self, meeting_url: str, display_name: str) -> JoinOutcome:
        self.limiter.check_and_record(meeting_url)
        try:
            page = await self._start_browser()
            await page.goto(meeting_url, wait_until="domcontentloaded", timeout=30_000)
            await self._fail_on_guard_page()
            name = await self._wait_for_prejoin(page)
            if name is not None:
                await name.fill(display_name)
            await self._configure_prejoin_media()

            ask = page.get_by_role("button", name=ASK_TO_JOIN_TEXT)
            if await ask.is_visible():
                await ask.click()
                await self._fail_on_guard_page()
                return JoinOutcome.ADMISSION_REQUESTED
            join = page.get_by_role("button", name=JOIN_BUTTON_TEXT)
            await join.wait_for(state="visible", timeout=15_000)
            await join.click()
            await self._wait_until_in_call(
                DIRECT_JOIN_TIMEOUT_SECONDS,
                timeout_code=FailureCode.MEETING_ACCESS_DENIED,
                timeout_detail="Google Meet did not complete the direct join",
            )
            return JoinOutcome.JOINED
        except InterviewerError:
            await self.leave()
            raise
        except Exception as exc:
            await self.leave()
            raise InterviewerError(
                FailureCode.BROWSER_DISCONNECTED,
                f"Could not join Google Meet safely: {exc}",
            ) from exc

    async def probe(self) -> str:
        try:
            page = await self._start_browser()
            user_agent = await page.evaluate("navigator.userAgent")
            if not isinstance(user_agent, str):
                raise RuntimeError("Browser did not provide a user agent")
            return user_agent
        finally:
            await self.leave()

    async def open_profile_setup(self) -> None:
        page = await self._start_browser()
        await page.goto(
            "https://accounts.google.com/",
            wait_until="domcontentloaded",
            timeout=30_000,
        )

    async def _wait_for_prejoin(self, page: Page) -> Locator | None:
        name = page.locator(GUEST_NAME_INPUT).first
        join = page.get_by_role("button", name=JOIN_BUTTON_TEXT)
        ask = page.get_by_role("button", name=ASK_TO_JOIN_TEXT)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            await self._fail_on_guard_page()
            if await name.is_visible():
                return name
            if await join.is_visible() or await ask.is_visible():
                return None
            await asyncio.sleep(0.25)
        body = compact_page_text(await page.locator("body").inner_text())
        raise InterviewerError(
            FailureCode.BROWSER_DISCONNECTED,
            f"Meet pre-join controls were not available. Visible page text: {body}",
        )

    async def wait_for_admission(self, timeout_seconds: int) -> None:
        await self._wait_until_in_call(
            timeout_seconds,
            timeout_code=FailureCode.MEETING_ADMISSION_TIMEOUT,
            timeout_detail="The host did not admit the interviewer before the admission timeout",
        )

    async def _wait_until_in_call(
        self,
        timeout_seconds: int,
        *,
        timeout_code: FailureCode,
        timeout_detail: str,
    ) -> None:
        page = self._require_page()
        leave_call = page.get_by_role("button", name=LEAVE_CALL_TEXT)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if page.is_closed():
                raise InterviewerError(
                    FailureCode.BROWSER_DISCONNECTED,
                    "Google Meet page closed while joining",
                )
            await self._fail_on_guard_page()
            if await leave_call.is_visible():
                return
            await asyncio.sleep(0.5)
        await self._fail_on_guard_page()
        raise InterviewerError(timeout_code, timeout_detail)

    async def _start_browser(self) -> Page:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        remove_browser_singleton_locks(self.profile_dir)
        self._playwright = await async_playwright().start()
        if self.connection_mode == "cdp":
            await self._launch_cdp_browser()
        else:
            await self._launch_playwright_browser()
        context = self._require_context()
        self._page = context.pages[0] if context.pages else await context.new_page()
        return self._page

    async def _launch_playwright_browser(self) -> None:
        if self._playwright is None:
            raise RuntimeError("Playwright is not running")
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=self.headless,
            channel=self.browser_channel,
            executable_path=self.browser_executable_path,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
            ],
            permissions=["microphone"],
            viewport={"width": 1280, "height": 800},
        )

    async def _launch_cdp_browser(self) -> None:
        if self._playwright is None:
            raise RuntimeError("Playwright is not running")
        executable = self.browser_executable_path or Path(self._playwright.chromium.executable_path)
        self._browser_process = await asyncio.create_subprocess_exec(
            str(executable),
            *chromium_cdp_args(
                profile_dir=self.profile_dir,
                port=self.cdp_port,
                headless=self.headless,
            ),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        endpoint = f"http://127.0.0.1:{self.cdp_port}"
        for _ in range(50):
            if self._browser_process.returncode is not None:
                raise RuntimeError(f"Chromium exited with code {self._browser_process.returncode}")
            try:
                self._browser = await self._playwright.chromium.connect_over_cdp(endpoint)
                break
            except Exception:
                await asyncio.sleep(0.2)
        if self._browser is None:
            raise RuntimeError("Timed out connecting Playwright to Chromium over CDP")
        if not self._browser.contexts:
            raise RuntimeError("Chromium did not expose its default browser context")
        self._context = self._browser.contexts[0]
        await self._context.grant_permissions(
            ["microphone"],
            origin="https://meet.google.com",
        )

    async def wait_for_participant(self, timeout_seconds: int) -> None:
        page = self._require_page()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if page.is_closed():
                raise InterviewerError(
                    FailureCode.BROWSER_DISCONNECTED,
                    "Google Meet page closed unexpectedly",
                )
            await self._fail_on_guard_page()
            labels = await page.locator("[aria-label]").evaluate_all(
                "elements => elements.map(element => element.getAttribute('aria-label') || '')"
            )
            count = participant_count_from_labels(labels)
            if count is not None and count >= 2:
                return
            body = await page.locator("body").inner_text()
            if not re.search(r"you are the only one|no one else is here", body, re.I):
                visible_people = page.locator("[data-participant-id]:visible")
                if await visible_people.count() >= 2:
                    return
            await asyncio.sleep(1)
        raise InterviewerError(
            FailureCode.PARTICIPANT_TIMEOUT,
            "No other participant appeared before the configured timeout",
        )

    async def participant_present(self) -> bool:
        page = self._require_page()
        if page.is_closed():
            raise InterviewerError(
                FailureCode.BROWSER_DISCONNECTED,
                "Google Meet page closed unexpectedly",
            )
        await self._fail_on_guard_page()
        labels = await page.locator("[aria-label]").evaluate_all(
            "elements => elements.map(element => element.getAttribute('aria-label') || '')"
        )
        count = participant_count_from_labels(labels)
        if count is not None:
            return count >= 2
        body = await page.locator("body").inner_text()
        if re.search(r"you are the only one|no one else is here", body, re.I):
            return False
        visible_people = page.locator("[data-participant-id]:visible")
        if await visible_people.count() >= 2:
            return True
        return True

    async def leave(self) -> None:
        if self._page is not None and not self._page.is_closed():
            button = self._page.get_by_role("button", name=LEAVE_CALL_TEXT)
            with suppress(Exception):
                if await button.is_visible():
                    await button.click(timeout=2_000)
        if self._context is not None and self.connection_mode == "playwright":
            with suppress(Exception):
                await self._context.close()
        if self._browser is not None:
            with suppress(Exception):
                async with asyncio.timeout(3):
                    await self._browser.close()
        if self._browser_process is not None and self._browser_process.returncode is None:
            self._browser_process.terminate()
            try:
                async with asyncio.timeout(5):
                    await self._browser_process.wait()
            except TimeoutError:
                self._browser_process.kill()
                await self._browser_process.wait()
        if self._playwright is not None:
            with suppress(Exception):
                await self._playwright.stop()
        remove_browser_singleton_locks(self.profile_dir)
        self._page = None
        self._context = None
        self._browser = None
        self._browser_process = None
        self._playwright = None

    async def _configure_prejoin_media(self) -> None:
        page = self._require_page()
        turn_on_mic = page.get_by_role("button", name=re.compile("turn on microphone", re.I))
        if await turn_on_mic.is_visible():
            await turn_on_mic.click()
        turn_off_camera = page.get_by_role("button", name=re.compile("turn off camera", re.I))
        if await turn_off_camera.is_visible():
            await turn_off_camera.click()

    async def _fail_on_guard_page(self) -> None:
        page = self._require_page()
        body = await page.locator("body").inner_text()
        failure = guard_page_failure(body)
        if failure is not None:
            code, detail = failure
            raise InterviewerError(code, detail)

    def _require_page(self) -> Page:
        if self._page is None:
            raise InterviewerError(
                FailureCode.BROWSER_DISCONNECTED,
                "Google Meet browser is not running",
            )
        return self._page

    def _require_context(self) -> BrowserContext:
        if self._context is None:
            raise InterviewerError(
                FailureCode.BROWSER_DISCONNECTED,
                "Google Meet browser context is not running",
            )
        return self._context
