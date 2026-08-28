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
    stt_model: str = "gpt-live-transcribe"
    llm_model: str = "gpt-5.6-luna"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "marin"
    reasoning_effort: Literal["none", "low", "medium", "high"] = "none"

    headless: bool = False
    participant_timeout_seconds: int = Field(default=300, ge=30, le=900)
    consent_timeout_seconds: int = Field(default=120, ge=30, le=300)
    response_timeout_seconds: int = Field(default=20, ge=5, le=60)
    maximum_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "sessions"
