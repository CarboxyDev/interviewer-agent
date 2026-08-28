from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict, deque
from contextlib import suppress

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

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


def participant_count_from_labels(labels: list[str]) -> int | None:
    counts = [int(match.group(1)) for label in labels if (match := PARTICIPANT_COUNT.search(label))]
    return max(counts) if counts else None


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
    def __init__(self, *, headless: bool, limiter: MeetingAttemptLimiter | None = None) -> None:
        self.headless = headless
        self.limiter = limiter or MeetingAttemptLimiter()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def join(self, meeting_url: str, display_name: str) -> None:
        self.limiter.check_and_record(meeting_url)
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--autoplay-policy=no-user-gesture-required",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--use-fake-ui-for-media-stream",
                ],
            )
            self._context = await self._browser.new_context(
                permissions=["microphone"],
                viewport={"width": 1280, "height": 800},
            )
            self._page = await self._context.new_page()
            await self._page.goto(meeting_url, wait_until="domcontentloaded", timeout=30_000)
            await self._fail_on_guard_page()
            name = self._page.get_by_role("textbox", name=re.compile("your name", re.I))
            await name.wait_for(state="visible", timeout=20_000)
            await name.fill(display_name)
            await self._configure_prejoin_media()

            ask = self._page.get_by_role("button", name=re.compile("ask to join", re.I))
            if await ask.is_visible():
                raise InterviewerError(
                    FailureCode.MEETING_NOT_OPEN,
                    "Meeting requires admission. Set meeting access to Open and start again later",
                )
            join = self._page.get_by_role("button", name=re.compile("join now", re.I))
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
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
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
