from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from voice_interviewer.domain import FailureCode, JoinOutcome
from voice_interviewer.errors import InterviewerError
from voice_interviewer.meet import (
    JOIN_BUTTON_TEXT,
    MeetingAttemptLimiter,
    PlaywrightMeetTransport,
    chromium_cdp_args,
    compact_page_text,
    guard_page_failure,
    participant_count_from_labels,
    remove_browser_singleton_locks,
)


class StubLocator:
    def __init__(self, *, visible: bool) -> None:
        self.visible = visible
        self.click = AsyncMock()
        self.wait_for = AsyncMock()

    async def is_visible(self) -> bool:
        return self.visible


class StubMeetPage:
    def __init__(self, *, ask_visible: bool, join_visible: bool, leave_visible: bool) -> None:
        self.ask = StubLocator(visible=ask_visible)
        self.join = StubLocator(visible=join_visible)
        self.leave = StubLocator(visible=leave_visible)
        self.goto = AsyncMock()

    def get_by_role(self, role: str, *, name: object) -> StubLocator:
        pattern = str(getattr(name, "pattern", name)).lower()
        if "ask to join" in pattern:
            return self.ask
        if "join now" in pattern:
            return self.join
        if "leave call" in pattern:
            return self.leave
        raise AssertionError(f"Unexpected role query: {role} {pattern}")

    def is_closed(self) -> bool:
        return False


@pytest.mark.parametrize("label", ["Join now", "Rejoin"])
def test_join_button_pattern_accepts_normal_meet_controls(label: str) -> None:
    assert JOIN_BUTTON_TEXT.search(label)


async def test_join_requests_manual_admission_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = StubMeetPage(ask_visible=True, join_visible=False, leave_visible=False)
    transport = PlaywrightMeetTransport(headless=True, profile_dir=tmp_path / "profile")
    monkeypatch.setattr(transport, "_start_browser", AsyncMock(return_value=page))
    monkeypatch.setattr(transport, "_wait_for_prejoin", AsyncMock(return_value=None))
    monkeypatch.setattr(transport, "_configure_prejoin_media", AsyncMock())
    monkeypatch.setattr(transport, "_fail_on_guard_page", AsyncMock())

    outcome = await transport.join(
        "https://meet.google.com/abc-defg-hij",
        "AI Interviewer",
    )

    assert outcome is JoinOutcome.ADMISSION_REQUESTED
    assert page.ask.click.await_count == 1
    assert page.join.click.await_count == 0


async def test_invited_account_joins_without_admission_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = StubMeetPage(ask_visible=False, join_visible=True, leave_visible=False)
    transport = PlaywrightMeetTransport(headless=True, profile_dir=tmp_path / "profile")
    wait_until_in_call = AsyncMock()
    monkeypatch.setattr(transport, "_start_browser", AsyncMock(return_value=page))
    monkeypatch.setattr(transport, "_wait_for_prejoin", AsyncMock(return_value=None))
    monkeypatch.setattr(transport, "_configure_prejoin_media", AsyncMock())
    monkeypatch.setattr(transport, "_fail_on_guard_page", AsyncMock())
    monkeypatch.setattr(transport, "_wait_until_in_call", wait_until_in_call)

    outcome = await transport.join(
        "https://meet.google.com/abc-defg-hij",
        "AI Interviewer",
    )

    assert outcome is JoinOutcome.JOINED
    assert page.join.click.await_count == 1
    wait_until_in_call.assert_awaited_once()


async def test_manual_admission_wait_completes_when_call_controls_appear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = StubMeetPage(ask_visible=False, join_visible=False, leave_visible=True)
    transport = PlaywrightMeetTransport(headless=True, profile_dir=tmp_path / "profile")
    transport._page = page  # type: ignore[assignment]
    monkeypatch.setattr(transport, "_fail_on_guard_page", AsyncMock())

    await transport.wait_for_admission(1)


async def test_manual_admission_timeout_has_stable_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = StubMeetPage(ask_visible=False, join_visible=False, leave_visible=False)
    transport = PlaywrightMeetTransport(headless=True, profile_dir=tmp_path / "profile")
    transport._page = page  # type: ignore[assignment]
    monkeypatch.setattr(transport, "_fail_on_guard_page", AsyncMock())

    with pytest.raises(InterviewerError) as caught:
        await transport.wait_for_admission(0)

    assert caught.value.code is FailureCode.MEETING_ADMISSION_TIMEOUT


def test_cdp_browser_is_loopback_only_and_uses_persistent_profile(tmp_path: Path) -> None:
    profile = tmp_path / "browser-profile"

    args = chromium_cdp_args(profile_dir=profile, port=9222, headless=False)

    assert "--remote-debugging-address=127.0.0.1" in args
    assert "--remote-debugging-port=9222" in args
    assert f"--user-data-dir={profile}" in args
    assert "--headless=new" not in args
    assert not any("AutomationControlled" in argument for argument in args)


def test_browser_singleton_cleanup_preserves_profile_data(tmp_path: Path) -> None:
    (tmp_path / "SingletonLock").symlink_to("old-container-123")
    preferences = tmp_path / "Preferences"
    preferences.write_text("keep", encoding="utf-8")

    remove_browser_singleton_locks(tmp_path)

    assert not (tmp_path / "SingletonLock").is_symlink()
    assert preferences.read_text(encoding="utf-8") == "keep"


def test_participant_count_uses_largest_accessible_label() -> None:
    assert participant_count_from_labels(["2 participants", "People, 3 participants"]) == 3
    assert participant_count_from_labels(["Chat", "Meeting details"]) is None


def test_page_diagnostic_is_compact_and_bounded() -> None:
    text = "  Join   this\nmeeting  " + ("x" * 500)

    assert compact_page_text(text, limit=30) == "Join this meeting " + ("x" * 12)


@pytest.mark.parametrize(
    ("body", "expected_code", "matched_text"),
    [
        (
            "You can't join this video call",
            FailureCode.MEETING_ACCESS_DENIED,
            "you can't join",
        ),
        (
            "No one responded to your request to join",
            FailureCode.MEETING_ACCESS_DENIED,
            "no one responded to your request",
        ),
        (
            "Please verify that you are human",
            FailureCode.GOOGLE_SECURITY_INTERVENTION,
            "verify that you are human",
        ),
    ],
)
def test_guard_page_failure_preserves_only_the_matched_reason(
    body: str,
    expected_code: FailureCode,
    matched_text: str,
) -> None:
    failure = guard_page_failure(body)

    assert failure is not None
    code, detail = failure
    assert code is expected_code
    assert matched_text in detail.lower()
    assert body not in detail


def test_regular_meet_page_is_not_a_guard_failure() -> None:
    assert guard_page_failure("Ready to join? Join now") is None


def test_meeting_attempt_limiter_enforces_cooldown() -> None:
    limiter = MeetingAttemptLimiter(cooldown_seconds=300, hourly_limit=3)
    limiter.check_and_record("https://meet.google.com/abc-defg-hij", now=100)

    with pytest.raises(InterviewerError) as caught:
        limiter.check_and_record("https://meet.google.com/abc-defg-hij", now=200)

    assert caught.value.code is FailureCode.MEETING_ACCESS_DENIED


def test_meeting_attempt_limiter_allows_attempt_after_cooldown() -> None:
    limiter = MeetingAttemptLimiter(cooldown_seconds=300, hourly_limit=3)
    limiter.check_and_record("https://meet.google.com/abc-defg-hij", now=100)

    limiter.check_and_record("https://meet.google.com/abc-defg-hij", now=400)


def test_meeting_attempt_limiter_can_be_disabled_for_an_authorized_demo() -> None:
    limiter = MeetingAttemptLimiter(cooldown_seconds=0, hourly_limit=0)

    for now in range(10):
        limiter.check_and_record("https://meet.google.com/abc-defg-hij", now=now)


def test_meeting_attempt_limiter_persists_cooldown_across_restart(tmp_path: Path) -> None:
    state_path = tmp_path / "meet-attempts.json"
    first = MeetingAttemptLimiter(state_path=state_path)
    first.check_and_record("https://meet.google.com/abc-defg-hij", now=100)

    restarted = MeetingAttemptLimiter(state_path=state_path)

    with pytest.raises(InterviewerError) as caught:
        restarted.check_and_record("https://meet.google.com/abc-defg-hij", now=200)

    assert caught.value.code is FailureCode.MEETING_ACCESS_DENIED
    assert "abc-defg-hij" not in state_path.read_text(encoding="utf-8")


def test_meeting_attempt_limiter_caps_profile_across_meeting_urls() -> None:
    limiter = MeetingAttemptLimiter(cooldown_seconds=300, hourly_limit=2)
    limiter.check_and_record("https://meet.google.com/abc-defg-hij", now=100)
    limiter.check_and_record("https://meet.google.com/xyz-abcd-efg", now=200)

    with pytest.raises(InterviewerError) as caught:
        limiter.check_and_record("https://meet.google.com/qrs-tuvw-xyz", now=400)

    assert caught.value.code is FailureCode.MEETING_ACCESS_DENIED
