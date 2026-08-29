from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="INTERVIEWER_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "production"] = "development"
    data_dir: Path = Path("data")
    database_url: str = "sqlite+aiosqlite:///data/interviewer.db"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"

    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "INTERVIEWER_OPENAI_API_KEY"),
        repr=False,
    )
    stt_model: str = "gpt-transcribe"
    llm_model: str = "gpt-5.6-luna"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "marin"
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "none"

    stt_language: str = Field(default="en", min_length=2, max_length=16)
    stt_delay: Literal["minimal", "low", "medium", "high", "xhigh"] = "low"
    stt_vad_threshold: float = Field(default=0.5, gt=0, lt=1)
    stt_prefix_padding_ms: int = Field(default=300, ge=0, le=2_000)
    stt_silence_duration_ms: int = Field(default=500, ge=100, le=5_000)
    stt_context_max_chars: int = Field(default=3_000, ge=0, le=10_000)
    stt_keyword_limit: int = Field(default=40, ge=0, le=100)
    transcript_clarification_attempts: int = Field(default=1, ge=0, le=3)

    headless: bool = False
    browser_profile_dir: Path = Path("data/browser-profile")
    browser_connection_mode: Literal["cdp", "playwright"] = "cdp"
    browser_cdp_port: int = Field(default=9222, ge=1024, le=65535)
    browser_channel: str | None = None
    browser_executable_path: Path | None = None
    participant_timeout_seconds: int = Field(default=300, ge=30, le=900)
    consent_timeout_seconds: int = Field(default=120, ge=30, le=300)
    response_timeout_seconds: int = Field(default=20, ge=5, le=60)
    candidate_turn_timeout_seconds: int = Field(default=120, ge=30, le=300)
    tts_timeout_seconds: int = Field(default=45, ge=5, le=120)
    maximum_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "sessions"
