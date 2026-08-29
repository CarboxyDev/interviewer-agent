from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict, deque
from contextlib import suppress
from pathlib import Path
from typing import Literal

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from voice_interviewer.domain import FailureCode
from voice_interviewer.errors import InterviewerError

SECURITY_TEXT = re.compile(
    r"captcha|unusual traffic|verify (that )?you are human|sign in to continue|couldn't let you in",
    re.IGNORECASE,
)
DENIAL_TEXT = re.compile(
    r"you can't join|not allowed to join|denied your request|removed from the meeting",
    re.IGNORECASE,
)
PARTICIPANT_COUNT = re.compile(r"\b(\d+)\s+(?:participant|people|person)", re.IGNORECASE)
GUEST_NAME_INPUT = (
    'input[placeholder*="name" i], input[aria-label*="name" i], input[name*="name" i]'
)
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


class MeetingAttemptLimiter:
    def __init__(self, *, cooldown_seconds: int = 300, hourly_limit: int = 3) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.hourly_limit = hourly_limit
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def check_and_record(self, meeting_url: str, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        attempts = self._attempts[meeting_url]
        while attempts and current - attempts[0] >= 3600:
            attempts.popleft()
        if attempts and current - attempts[-1] < self.cooldown_seconds:
            raise InterviewerError(
                FailureCode.MEETING_ACCESS_DENIED,
                "Meet join cooldown is active; no automated retry was attempted",
            )
        if len(attempts) >= self.hourly_limit:
            raise InterviewerError(
                FailureCode.MEETING_ACCESS_DENIED,
                "Meet join limit reached for this URL; no automated retry was attempted",
            )
        attempts.append(current)


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
        self.limiter = limiter or MeetingAttemptLimiter()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._browser_process: asyncio.subprocess.Process | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def join(self, meeting_url: str, display_name: str) -> None:
        self.limiter.check_and_record(meeting_url)
        try:
            page = await self._start_browser()
            await page.goto(meeting_url, wait_until="domcontentloaded", timeout=30_000)
            await self._fail_on_guard_page()
            name = page.locator(GUEST_NAME_INPUT).first
            try:
                await name.wait_for(state="visible", timeout=20_000)
            except PlaywrightTimeoutError as exc:
                await self._fail_on_guard_page()
                body = compact_page_text(await page.locator("body").inner_text())
                raise InterviewerError(
                    FailureCode.BROWSER_DISCONNECTED,
                    f"Guest name field was not available. Visible page text: {body}",
                ) from exc
            await name.fill(display_name)
            await self._configure_prejoin_media()

            ask = page.get_by_role("button", name=re.compile("ask to join", re.I))
            if await ask.is_visible():
                raise InterviewerError(
                    FailureCode.MEETING_NOT_OPEN,
                    "Meeting requires admission. Set meeting access to Open and start again later",
                )
            join = page.get_by_role("button", name=re.compile("join now", re.I))
            await join.wait_for(state="visible", timeout=15_000)
            await join.click()
            await asyncio.sleep(2)
            await self._fail_on_guard_page()
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

    async def leave(self) -> None:
        if self._page is not None and not self._page.is_closed():
            button = self._page.get_by_role("button", name=re.compile("leave call", re.I))
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
        if SECURITY_TEXT.search(body):
            raise InterviewerError(
                FailureCode.GOOGLE_SECURITY_INTERVENTION,
                "Google requested an account or security check. The bot will not bypass it",
            )
        if DENIAL_TEXT.search(body):
            raise InterviewerError(
                FailureCode.MEETING_ACCESS_DENIED,
                "Google Meet denied or removed the guest participant",
            )

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
