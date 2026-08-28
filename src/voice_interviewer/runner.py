from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import suppress

from voice_interviewer.conversation import (
    CONSENT_DISCLOSURE,
    build_transcription_hints,
    classify_consent,
    is_consent_withdrawal,
    transcript_needs_clarification,
)
from voice_interviewer.documents import extract_document
from voice_interviewer.domain import (
    ConsentDecision,
    FailureCode,
    Session,
    SessionState,
    Speaker,
    SpeechEvent,
    SpeechEventKind,
    Utterance,
)
from voice_interviewer.errors import ConsentWithdrawnError, InterviewerError
from voice_interviewer.ports import (
    ArtifactStore,
    AudioRouter,
    Interviewer,
    MeetTransport,
    SessionRepository,
    SpeechToText,
    TextToSpeech,
)


class ConversationRunner:
    def __init__(
        self,
        *,
        repository: SessionRepository,
        artifacts: ArtifactStore,
        meet: MeetTransport,
        audio: AudioRouter,
        stt: SpeechToText,
        interviewer: Interviewer,
        tts: TextToSpeech,
        participant_timeout_seconds: int,
        consent_timeout_seconds: int,
        response_timeout_seconds: int,
        tts_timeout_seconds: int,
        stt_context_max_chars: int,
        stt_keyword_limit: int,
        transcript_clarification_attempts: int,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.meet = meet
        self.audio = audio
        self.stt = stt
        self.interviewer = interviewer
        self.tts = tts
        self.participant_timeout_seconds = participant_timeout_seconds
        self.consent_timeout_seconds = consent_timeout_seconds
        self.response_timeout_seconds = response_timeout_seconds
        self.tts_timeout_seconds = tts_timeout_seconds
        self.stt_context_max_chars = stt_context_max_chars
        self.stt_keyword_limit = stt_keyword_limit
        self.transcript_clarification_attempts = transcript_clarification_attempts
        self._stop_requested = asyncio.Event()

    async def stop(self, session_id: str) -> None:
        self._stop_requested.set()
        await self.audio.stop_bot_audio()
        await self.meet.leave()

    async def run(self, session_id: str) -> None:
        self._stop_requested.clear()
        consented = False
        recording_started = False
        try:
            session = await self.repository.get(session_id)
            if session is None:
                return
            await self.repository.transition(session_id, SessionState.PREPARING)
            input_dir = self.artifacts.session_dir(session_id) / "input"
            resume_path = input_dir / session.resume_name
            job_path = input_dir / session.job_description_name
            resume_text, job_text = await asyncio.gather(
                extract_document(resume_path),
                extract_document(job_path),
            )
            plan = await self.interviewer.prepare(
                resume_text=resume_text,
                job_description_text=job_text,
                duration_minutes=session.duration_minutes,
            )

            self._raise_if_stopped()
            await self.repository.transition(session_id, SessionState.JOINING)
            await self.meet.join(session.meeting_url, "AI Interviewer")
            await self.repository.transition(session_id, SessionState.WAITING_FOR_PARTICIPANT)
            await self.meet.wait_for_participant(self.participant_timeout_seconds)
            await self.repository.transition(session_id, SessionState.AWAITING_CONSENT)

            transcription_hints = build_transcription_hints(
                resume_text=resume_text,
                job_description_text=job_text,
                max_chars=self.stt_context_max_chars,
                keyword_limit=self.stt_keyword_limit,
            )
            speech_events = self.stt.transcribe(
                self.audio.candidate_audio(),
                hints=transcription_hints,
            )
            consent_text = await self._obtain_consent(speech_events)
            decision = classify_consent(consent_text)
            if decision is not ConsentDecision.GRANTED:
                await self.artifacts.delete_content(session_id)
                await self.repository.transition(
                    session_id,
                    SessionState.STOPPED,
                    detail="Candidate did not grant recording consent",
                )
                return

            session = await self.repository.set_consent(session_id)
            consented = True
            await self.audio.start_recording(self.artifacts.session_dir(session_id))
            recording_started = True
            await self.repository.transition(session_id, SessionState.ACTIVE)
            transcript = await self._conduct_interview(session, plan, speech_events, consent_text)
            await self.repository.transition(session_id, SessionState.FINALIZING)
            await self.audio.stop_recording()
            recording_started = False
            notes = await self.interviewer.notes(transcript)
            session = await self.repository.get(session_id)
            if session is None:
                return
            await self.artifacts.write_outputs(session, transcript, notes)
            await self.repository.transition(session_id, SessionState.COMPLETED)
            completed = await self.repository.get(session_id)
            if completed is not None:
                await self.artifacts.write_outputs(completed, transcript, notes)
        except asyncio.CancelledError:
            await self._stop_session(session_id)
            raise
        except ConsentWithdrawnError:
            if recording_started:
                with suppress(Exception):
                    await self.audio.stop_recording()
                recording_started = False
            await self.artifacts.delete_content(session_id)
            await self.repository.transition(
                session_id,
                SessionState.STOPPED,
                detail="Candidate withdrew recording consent",
            )
        except InterviewerError as exc:
            await self.repository.fail(session_id, exc.code, exc.detail)
        except TimeoutError as exc:
            code = FailureCode.CONSENT_TIMEOUT if not consented else FailureCode.INTERNAL_ERROR
            await self.repository.fail(session_id, code, str(exc))
        except Exception as exc:
            await self.repository.fail(session_id, FailureCode.INTERNAL_ERROR, str(exc)[:500])
        finally:
            if recording_started:
                with suppress(Exception):
                    await self.audio.stop_recording()
            with suppress(Exception):
                await self.meet.leave()

    async def _obtain_consent(self, events: AsyncIterator[SpeechEvent]) -> str:
        prompt = CONSENT_DISCLOSURE
        for attempt in range(2):
            response = await self._say_and_receive(
                prompt,
                events,
                timeout_seconds=self.consent_timeout_seconds,
            )
            decision = classify_consent(response)
            if decision is not ConsentDecision.UNCLEAR:
                return response
            if attempt == 0:
                prompt = (
                    "I need an explicit yes or no. Do you consent to recording and transcription?"
                )
        return response

    async def _conduct_interview(
        self,
        session: Session,
        plan: str,
        events: AsyncIterator[SpeechEvent],
        consent_text: str,
    ) -> list[Utterance]:
        duration_minutes = session.duration_minutes
        transcript: list[Utterance] = [
            Utterance(Speaker.INTERVIEWER, CONSENT_DISCLOSURE, 0, 0),
            Utterance(Speaker.CANDIDATE, consent_text, 0, 0),
        ]
        started = time.monotonic()
        duration_seconds = duration_minutes * 60
        while not self._stop_requested.is_set():
            elapsed = int(time.monotonic() - started)
            remaining = max(0, duration_seconds - elapsed)
            turn = await self.interviewer.next_turn(
                plan=plan,
                transcript=transcript,
                seconds_remaining=remaining,
            )
            turn_started = int((time.monotonic() - started) * 1000)
            transcript.append(Utterance(Speaker.INTERVIEWER, turn.say, turn_started, turn_started))
            if turn.should_end or remaining <= 0:
                await self._play_with_timeout(turn.say)
                break
            response = await self._say_and_receive(
                turn.say,
                events,
                timeout_seconds=self.response_timeout_seconds,
            )
            response_ended = int((time.monotonic() - started) * 1000)
            self._raise_if_consent_withdrawn(response)
            transcript.append(Utterance(Speaker.CANDIDATE, response, turn_started, response_ended))
            for _ in range(self.transcript_clarification_attempts):
                if not transcript_needs_clarification(response):
                    break
                clarification = (
                    "I may not have heard that clearly. Could you please repeat your answer?"
                )
                clarification_started = int((time.monotonic() - started) * 1000)
                transcript.append(
                    Utterance(
                        Speaker.INTERVIEWER,
                        clarification,
                        clarification_started,
                        clarification_started,
                    )
                )
                response = await self._say_and_receive(
                    clarification,
                    events,
                    timeout_seconds=self.response_timeout_seconds,
                )
                response_ended = int((time.monotonic() - started) * 1000)
                self._raise_if_consent_withdrawn(response)
                transcript.append(
                    Utterance(
                        Speaker.CANDIDATE,
                        response,
                        clarification_started,
                        response_ended,
                    )
                )
        self._raise_if_stopped()
        return transcript

    async def _say_and_receive(
        self,
        text: str,
        events: AsyncIterator[SpeechEvent],
        *,
        timeout_seconds: int,
    ) -> str:
        playback = asyncio.create_task(self.audio.play_bot_audio(self.tts.synthesize(text)))
        event_task: asyncio.Task[SpeechEvent] | None = None
        playback_deadline = time.monotonic() + self.tts_timeout_seconds
        response_deadline: float | None = None
        try:
            while True:
                self._raise_if_stopped()
                if playback.done() and response_deadline is None:
                    playback.result()
                    response_deadline = time.monotonic() + timeout_seconds
                if event_task is None:
                    event_task = asyncio.create_task(_next_event(events))
                waiting: set[asyncio.Task[object]] = {event_task}
                if response_deadline is None:
                    waiting.add(playback)
                deadline = response_deadline or playback_deadline
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if response_deadline is None:
                        raise TimeoutError("Timed out playing interviewer speech")
                    raise TimeoutError("Timed out waiting for candidate speech")
                done, _ = await asyncio.wait(
                    waiting,
                    timeout=remaining,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    if response_deadline is None:
                        raise TimeoutError("Timed out playing interviewer speech")
                    raise TimeoutError("Timed out waiting for candidate speech")
                if event_task in done:
                    event = event_task.result()
                    event_task = None
                    if event.kind is SpeechEventKind.SPEECH_STARTED:
                        if not playback.done():
                            await self._stop_playback(playback)
                        response_deadline = time.monotonic() + timeout_seconds
                    elif event.kind is SpeechEventKind.FINAL_TRANSCRIPT:
                        if not playback.done():
                            await self._stop_playback(playback)
                        return event.text
                if playback in done:
                    playback.result()
                    if response_deadline is None:
                        response_deadline = time.monotonic() + timeout_seconds
        finally:
            if event_task is not None and not event_task.done():
                event_task.cancel()
            if not playback.done():
                await self.audio.stop_bot_audio()
                playback.cancel()
            with suppress(asyncio.CancelledError):
                await playback

    async def _stop_playback(self, playback: asyncio.Task[None]) -> None:
        await self.audio.stop_bot_audio()
        if not playback.done():
            playback.cancel()
        with suppress(asyncio.CancelledError):
            await playback

    async def _play_with_timeout(self, text: str) -> None:
        try:
            async with asyncio.timeout(self.tts_timeout_seconds):
                await self.audio.play_bot_audio(self.tts.synthesize(text))
        except TimeoutError as exc:
            await self.audio.stop_bot_audio()
            raise TimeoutError("Timed out playing interviewer speech") from exc

    @staticmethod
    def _raise_if_consent_withdrawn(response: str) -> None:
        if is_consent_withdrawal(response):
            raise ConsentWithdrawnError

    def _raise_if_stopped(self) -> None:
        if self._stop_requested.is_set():
            raise asyncio.CancelledError

    async def _stop_session(self, session_id: str) -> None:
        session = await self.repository.get(session_id)
        if session and session.state not in {
            SessionState.COMPLETED,
            SessionState.STOPPED,
            SessionState.FAILED,
        }:
            await self.repository.transition(session_id, SessionState.STOPPED, detail="Stopped")


async def _next_event(events: AsyncIterator[SpeechEvent]) -> SpeechEvent:
    return await anext(events)
