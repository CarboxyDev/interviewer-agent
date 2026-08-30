from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from voice_interviewer.domain import (
    AnswerQuality,
    InterviewNotes,
    JoinOutcome,
    NextTurn,
    ResponseMode,
    SessionState,
    SpeechEvent,
    TranscriptionHints,
    Utterance,
)
from voice_interviewer.persistence import SqlAlchemySessionRepository


class HoldingRunner:
    def __init__(self, repository: SqlAlchemySessionRepository) -> None:
        self.repository = repository
        self.released = asyncio.Event()

    async def run(self, session_id: str) -> None:
        await self.released.wait()

    async def stop(self, session_id: str) -> None:
        self.released.set()
        session = await self.repository.get(session_id)
        if session and session.state not in {
            SessionState.COMPLETED,
            SessionState.STOPPED,
            SessionState.FAILED,
        }:
            await self.repository.transition(session_id, SessionState.STOPPED)


class FakeMeet:
    def __init__(
        self,
        join_outcome: JoinOutcome = JoinOutcome.JOINED,
        *,
        participant_present: bool = True,
    ) -> None:
        self.joined = False
        self.left = False
        self.join_outcome = join_outcome
        self.admission_waited = False
        self.participant_is_present = participant_present

    async def join(self, meeting_url: str) -> JoinOutcome:
        self.joined = meeting_url.endswith("abc-defg-hij")
        return self.join_outcome

    async def wait_for_admission(self, timeout_seconds: int) -> None:
        self.admission_waited = True

    async def wait_for_participant(self, timeout_seconds: int) -> None:
        return None

    async def participant_present(self) -> bool:
        return self.participant_is_present

    async def leave(self) -> None:
        self.left = True


class FakeAudio:
    def __init__(self) -> None:
        self.stops = 0
        self.recorded = False
        self.session_dir: Path | None = None

    async def candidate_audio(self) -> AsyncIterator[bytes]:
        while True:
            yield b"\x00\x00" * 100
            await asyncio.sleep(0)

    async def play_bot_audio(self, audio: AsyncIterator[bytes]) -> None:
        async for _ in audio:
            await asyncio.sleep(0.001)

    async def stop_bot_audio(self) -> None:
        self.stops += 1

    async def start_recording(self, session_dir: Path) -> None:
        self.recorded = True
        self.session_dir = session_dir
        (session_dir / "interview.mp3").write_bytes(b"fake mp3")

    async def stop_recording(self) -> Path | None:
        self.recorded = False
        return self.session_dir / "interview.mp3" if self.session_dir else None


class FakeSTT:
    def __init__(self, events: Sequence[SpeechEvent], *, hold_open: bool = False) -> None:
        self.events = events
        self.hold_open = hold_open
        self.hints: TranscriptionHints | None = None

    async def transcribe(
        self,
        audio: AsyncIterator[bytes],
        *,
        hints: TranscriptionHints | None = None,
    ) -> AsyncIterator[SpeechEvent]:
        self.hints = hints
        for event in self.events:
            yield event
            await asyncio.sleep(0)
        if self.hold_open:
            await asyncio.Event().wait()


class FakeInterviewer:
    async def prepare(
        self,
        *,
        resume_text: str,
        job_description_text: str,
        duration_minutes: int,
    ) -> str:
        return "Ask about API design, tradeoffs, and evidence."

    async def next_turn(
        self,
        *,
        plan: str,
        transcript: Sequence[Utterance],
        seconds_remaining: int,
    ) -> NextTurn:
        candidate_answers = [item for item in transcript if item.speaker.value == "candidate"]
        if len(candidate_answers) == 2:
            return NextTurn(
                say="Tell me about an API you designed.",
                rationale="Gather relevant evidence.",
                topic="API design",
                answer_quality=AnswerQuality.SUBSTANTIVE,
                response_mode=ResponseMode.FOLLOW_UP,
                should_end=False,
            )
        return NextTurn(
            say="What if the external call succeeded but the database write failed?",
            rationale="Simulate a malformed ending turn from the model.",
            topic="Close",
            answer_quality=AnswerQuality.SUBSTANTIVE,
            response_mode=ResponseMode.END,
            should_end=True,
        )

    async def notes(self, transcript: Sequence[Utterance]) -> InterviewNotes:
        return InterviewNotes(
            summary="The candidate discussed API design.",
            strengths_observed=["Explained a concrete API"],
            areas_to_probe=[],
            evidence=["Candidate described an API they designed"],
        )


class FakeTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        self.spoken.append(text)
        for _ in range(5):
            yield b"\x00\x00" * 100
            await asyncio.sleep(0.001)
