from pathlib import Path

import pytest

from voice_interviewer.domain import FailureCode
from voice_interviewer.errors import InterviewerError
from voice_interviewer.meet import (
    JOIN_BUTTON_TEXT,
    MeetingAttemptLimiter,
    chromium_cdp_args,
    compact_page_text,
    guard_page_failure,
    participant_count_from_labels,
    remove_browser_singleton_locks,
)


@pytest.mark.parametrize("label", ["Join now", "Rejoin"])
def test_join_button_pattern_accepts_normal_meet_controls(label: str) -> None:
    assert JOIN_BUTTON_TEXT.search(label)


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
