from pathlib import Path

import pytest

from voice_interviewer.domain import FailureCode
from voice_interviewer.errors import InterviewerError
from voice_interviewer.meet import (
    MeetingAttemptLimiter,
    chromium_cdp_args,
    compact_page_text,
    participant_count_from_labels,
    remove_browser_singleton_locks,
)


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
