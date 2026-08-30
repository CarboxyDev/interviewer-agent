from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class SessionState(StrEnum):
    CREATED = "CREATED"
    PREPARING = "PREPARING"
    JOINING = "JOINING"
    AWAITING_ADMISSION = "AWAITING_ADMISSION"
    WAITING_FOR_PARTICIPANT = "WAITING_FOR_PARTICIPANT"
    AWAITING_CONSENT = "AWAITING_CONSENT"
    ACTIVE = "ACTIVE"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


TERMINAL_STATES = {SessionState.COMPLETED, SessionState.STOPPED, SessionState.FAILED}

ALLOWED_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.CREATED: {SessionState.PREPARING, SessionState.STOPPED, SessionState.FAILED},
    SessionState.PREPARING: {SessionState.JOINING, SessionState.STOPPED, SessionState.FAILED},
    SessionState.JOINING: {
        SessionState.AWAITING_ADMISSION,
        SessionState.WAITING_FOR_PARTICIPANT,
        SessionState.STOPPED,
        SessionState.FAILED,
    },
    SessionState.AWAITING_ADMISSION: {
        SessionState.WAITING_FOR_PARTICIPANT,
        SessionState.STOPPED,
        SessionState.FAILED,
    },
    SessionState.WAITING_FOR_PARTICIPANT: {
        SessionState.AWAITING_CONSENT,
        SessionState.STOPPED,
        SessionState.FAILED,
    },
    SessionState.AWAITING_CONSENT: {
        SessionState.ACTIVE,
        SessionState.STOPPED,
        SessionState.FAILED,
    },
    SessionState.ACTIVE: {
        SessionState.FINALIZING,
        SessionState.STOPPED,
        SessionState.FAILED,
    },
    SessionState.FINALIZING: {
        SessionState.COMPLETED,
        SessionState.STOPPED,
        SessionState.FAILED,
    },
    SessionState.COMPLETED: set(),
    SessionState.STOPPED: set(),
    SessionState.FAILED: set(),
}


class FailureCode(StrEnum):
    MEETING_NOT_OPEN = "MEETING_NOT_OPEN"
    MEETING_ACCESS_DENIED = "MEETING_ACCESS_DENIED"
    MEETING_ADMISSION_TIMEOUT = "MEETING_ADMISSION_TIMEOUT"
    GOOGLE_SECURITY_INTERVENTION = "GOOGLE_SECURITY_INTERVENTION"
    PARTICIPANT_TIMEOUT = "PARTICIPANT_TIMEOUT"
    CONSENT_DECLINED = "CONSENT_DECLINED"
    CONSENT_TIMEOUT = "CONSENT_TIMEOUT"
    OPENAI_UNAVAILABLE = "OPENAI_UNAVAILABLE"
    AUDIO_DEVICE_FAILURE = "AUDIO_DEVICE_FAILURE"
    BROWSER_DISCONNECTED = "BROWSER_DISCONNECTED"
    INVALID_DOCUMENT = "INVALID_DOCUMENT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class JoinOutcome(StrEnum):
    JOINED = "JOINED"
    ADMISSION_REQUESTED = "ADMISSION_REQUESTED"


class Speaker(StrEnum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class SpeechEventKind(StrEnum):
    SPEECH_STARTED = "SPEECH_STARTED"
    FINAL_TRANSCRIPT = "FINAL_TRANSCRIPT"


class ConsentDecision(StrEnum):
    GRANTED = "GRANTED"
    DECLINED = "DECLINED"
    UNCLEAR = "UNCLEAR"


class SessionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    meeting_url: HttpUrl
    duration_minutes: int = Field(default=30, ge=5, le=45)
    meeting_authorization_confirmed: bool

    @field_validator("meeting_url")
    @classmethod
    def validate_meeting_url(cls, value: HttpUrl) -> HttpUrl:
        host = (value.host or "").lower()
        if host != "meet.google.com":
            raise ValueError("meeting_url must use https://meet.google.com")
        if value.scheme != "https":
            raise ValueError("meeting_url must use HTTPS")
        code = (value.path or "").strip("/")
        if not __import__("re").fullmatch(r"[a-zA-Z]{3}-[a-zA-Z]{4}-[a-zA-Z]{3}", code):
            raise ValueError("meeting_url must contain a standard Google Meet code")
        return HttpUrl(f"https://meet.google.com/{code.lower()}")

    @field_validator("meeting_authorization_confirmed")
    @classmethod
    def require_authorization(cls, value: bool) -> bool:
        if not value:
            raise ValueError("meeting owner authorization must be confirmed")
        return value


@dataclass(slots=True)
class Session:
    meeting_url: str
    duration_minutes: int
    resume_name: str
    job_description_name: str
    id: UUID = field(default_factory=uuid4)
    state: SessionState = SessionState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    consented_at: datetime | None = None
    ended_at: datetime | None = None
    failure_code: FailureCode | None = None
    failure_detail: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedInterview:
    session: Session
    resume_path: Path
    job_description_path: Path
    resume_text: str
    job_description_text: str


@dataclass(frozen=True, slots=True)
class Utterance:
    speaker: Speaker
    text: str
    started_at_ms: int
    ended_at_ms: int


@dataclass(frozen=True, slots=True)
class SpeechEvent:
    kind: SpeechEventKind
    text: str = ""
    item_id: str | None = None


@dataclass(frozen=True, slots=True)
class TranscriptionHints:
    prompt: str = ""
    keywords: tuple[str, ...] = ()


class NextTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    say: str = Field(min_length=1, max_length=800)
    rationale: str = Field(min_length=1, max_length=500)
    topic: str = Field(min_length=1, max_length=100)
    should_end: bool


class InterviewNotes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    strengths_observed: list[str] = Field(max_length=8)
    areas_to_probe: list[str] = Field(max_length=8)
    evidence: list[str] = Field(max_length=12)


class SessionView(BaseModel):
    id: UUID
    state: SessionState
    duration_minutes: int
    resume_name: str
    job_description_name: str
    created_at: datetime
    updated_at: datetime
    consented_at: datetime | None
    ended_at: datetime | None
    failure_code: FailureCode | None
    failure_detail: str | None

    @classmethod
    def from_session(cls, session: Session) -> SessionView:
        return cls(
            id=session.id,
            state=session.state,
            duration_minutes=session.duration_minutes,
            resume_name=session.resume_name,
            job_description_name=session.job_description_name,
            created_at=session.created_at,
            updated_at=session.updated_at,
            consented_at=session.consented_at,
            ended_at=session.ended_at,
            failure_code=session.failure_code,
            failure_detail=session.failure_detail,
        )


class SessionPage(BaseModel):
    items: list[SessionView]
    total: int
    limit: int
    offset: int


class ArtifactView(BaseModel):
    name: str
    size_bytes: int


class HealthView(BaseModel):
    status: Literal["ok", "not_ready"]
    checks: dict[str, Any]
