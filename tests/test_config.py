from pathlib import Path

import pytest
from pydantic import ValidationError

from voice_interviewer.config import Settings


def test_model_and_pipeline_controls_are_configurable() -> None:
    settings = Settings(
        _env_file=None,
        reasoning_effort="max",
        stt_delay="minimal",
        stt_vad_threshold=0.65,
        stt_context_max_chars=0,
        transcript_clarification_attempts=0,
        candidate_turn_timeout_seconds=180,
        candidate_turn_grace_seconds=1.5,
        browser_profile_dir="custom/profile",
        browser_connection_mode="playwright",
        browser_cdp_port=9333,
        browser_channel="chrome",
        browser_executable_path="/opt/browser/chrome",
    )

    assert settings.reasoning_effort == "max"
    assert settings.stt_delay == "minimal"
    assert settings.stt_vad_threshold == 0.65
    assert settings.stt_context_max_chars == 0
    assert settings.transcript_clarification_attempts == 0
    assert settings.candidate_turn_timeout_seconds == 180
    assert settings.candidate_turn_grace_seconds == 1.5
    assert settings.browser_profile_dir == Path("custom/profile")
    assert settings.browser_connection_mode == "playwright"
    assert settings.browser_cdp_port == 9333
    assert settings.browser_channel == "chrome"
    assert settings.browser_executable_path == Path("/opt/browser/chrome")


def test_default_stt_model_supports_server_side_turn_detection() -> None:
    assert Settings(_env_file=None).stt_model == "gpt-transcribe"


def test_invalid_vad_threshold_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, stt_vad_threshold=1.5)
