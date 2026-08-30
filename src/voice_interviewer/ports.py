from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from voice_interviewer.domain import (
    InterviewNotes,
    JoinOutcome,
    NextTurn,
    Session,
    SessionState,
    SpeechEvent,
    TranscriptionHints,
    Utterance,
)


class SessionRepository(Protocol):
    async def initialize(self) -> None: ...

    async def create(self, session: Session) -> Session: ...

    async def get(self, session_id: str) -> Session | None: ...

    async def list_recent(self, *, limit: int, offset: int) -> tuple[list[Session], int]: ...

    async def transition(
        self,
        session_id: str,
        target: SessionState,
        *,
        detail: str | None = None,
    ) -> Session: ...

    async def set_consent(self, session_id: str) -> Session: ...

    async def fail(self, session_id: str, code: str, detail: str) -> Session: ...

    async def has_active(self) -> bool: ...

    async def fail_interrupted(self) -> int: ...

    async def delete(self, session_id: str) -> bool: ...


class ArtifactStore(Protocol):
    async def prepare_inputs(
        self,
        session_id: str,
        *,
        resume_name: str,
        resume: bytes,
        job_description_name: str,
        job_description: bytes,
    ) -> tuple[Path, Path]: ...

    async def list(self, session_id: str) -> list[Path]: ...

    def session_dir(self, session_id: str) -> Path: ...

    async def write_outputs(
        self,
        session: Session,
        transcript: Sequence[Utterance],
        notes: InterviewNotes,
        metrics: Mapping[str, object],
    ) -> None: ...

    async def delete_content(self, session_id: str) -> None: ...

    async def delete_all(self, session_id: str) -> None: ...


class MeetTransport(Protocol):
    async def join(self, meeting_url: str, display_name: str) -> JoinOutcome: ...

    async def wait_for_admission(self, timeout_seconds: int) -> None: ...

    async def wait_for_participant(self, timeout_seconds: int) -> None: ...

    async def participant_present(self) -> bool: ...

    async def leave(self) -> None: ...


class SpeechToText(Protocol):
    def transcribe(
        self,
        audio: AsyncIterator[bytes],
        *,
        hints: TranscriptionHints | None = None,
    ) -> AsyncIterator[SpeechEvent]: ...


class Interviewer(Protocol):
    async def prepare(
        self,
        *,
        resume_text: str,
        job_description_text: str,
        duration_minutes: int,
    ) -> str: ...

    async def next_turn(
        self,
        *,
        plan: str,
        transcript: Sequence[Utterance],
        seconds_remaining: int,
    ) -> NextTurn: ...

    async def notes(self, transcript: Sequence[Utterance]) -> InterviewNotes: ...


class TextToSpeech(Protocol):
    def synthesize(self, text: str) -> AsyncIterator[bytes]: ...


class AudioRouter(Protocol):
    def candidate_audio(self) -> AsyncIterator[bytes]: ...

    async def play_bot_audio(self, audio: AsyncIterator[bytes]) -> None: ...

    async def stop_bot_audio(self) -> None: ...

    async def start_recording(self, session_dir: Path) -> None: ...

    async def stop_recording(self) -> Path | None: ...


class InterviewRunner(Protocol):
    async def run(self, session_id: str) -> None: ...

    async def stop(self, session_id: str) -> None: ...


class ReadinessProbe(Protocol):
    async def checks(self) -> dict[str, object]: ...
