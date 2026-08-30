from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable
from contextlib import suppress
from typing import TypeVar

from voice_interviewer.conversation import (
    CONSENT_DECLINED_CLOSING,
    CONSENT_DISCLOSURE,
    CONSENT_WITHDRAWAL_CLOSING,
    INTERVIEW_CLOSING,
    TIME_LIMIT_CLOSING,
    build_transcription_hints,
    classify_consent,
    final_question_prompt,
    interview_opening,
    is_consent_withdrawal,
    is_interview_end_request,
    is_repeat_request,
    is_thinking_request,
    repeat_prompt,
    transcript_needs_clarification,
)
from voice_interviewer.documents import extract_document
from voice_interviewer.domain import (
    ConsentDecision,
    FailureCode,
    InterviewNotes,
    JoinOutcome,
    Session,
    SessionState,
    Speaker,
    SpeechEvent,
    SpeechEventKind,
    Utterance,
)
from voice_interviewer.errors import ConsentWithdrawnError, InterviewerError, ParticipantLeftError
from voice_interviewer.metrics import LatencyTracker
from voice_interviewer.ports import (
    ArtifactStore,
    AudioRouter,
    Interviewer,
    MeetTransport,
    SessionRepository,
    SpeechToText,
    TextToSpeech,
)

T = TypeVar("T")

INTERVIEW_CLOSING_RESERVE_SECONDS = 20
INTERVIEW_FINAL_QUESTION_WINDOW_SECONDS = 90


class SpeechEventCursor:
    """Keeps one pending read alive while the conversation moves between turns."""

    def __init__(self, source: AsyncIterator[SpeechEvent]) -> None:
        self.source = source
        self._pending: asyncio.Task[SpeechEvent] | None = None

    def next_task(self) -> asyncio.Task[SpeechEvent]:
        if self._pending is None:
            self._pending = asyncio.create_task(_next_event(self.source))
        return self._pending

    def consume(self, task: asyncio.Task[SpeechEvent]) -> SpeechEvent:
        if task is not self._pending:
            raise RuntimeError("Speech event task does not belong to this cursor")
        try:
            return task.result()
        finally:
            self._pending = None

    async def close(self) -> None:
        pending = self._pending
        self._pending = None
        if pending is not None:
            if not pending.done():
                pending.cancel()
            with suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending
        close = getattr(self.source, "aclose", None)
        if close is not None:
            with suppress(asyncio.CancelledError, RuntimeError):
                await close()


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
        admission_timeout_seconds: int,
        participant_timeout_seconds: int,
        consent_timeout_seconds: int,
        response_timeout_seconds: float,
        candidate_turn_timeout_seconds: float,
        candidate_turn_grace_seconds: float,
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
        self.admission_timeout_seconds = admission_timeout_seconds
        self.participant_timeout_seconds = participant_timeout_seconds
        self.consent_timeout_seconds = consent_timeout_seconds
        self.response_timeout_seconds = response_timeout_seconds
        self.candidate_turn_timeout_seconds = candidate_turn_timeout_seconds
        self.candidate_turn_grace_seconds = candidate_turn_grace_seconds
        self.tts_timeout_seconds = tts_timeout_seconds
        self.stt_context_max_chars = stt_context_max_chars
        self.stt_keyword_limit = stt_keyword_limit
        self.transcript_clarification_attempts = transcript_clarification_attempts
        self._stop_requested = asyncio.Event()
        self._metric_models = {
            stage: str(model)
            for stage, adapter in (("stt", stt), ("llm", interviewer), ("tts", tts))
            if (model := getattr(adapter, "model", None)) is not None
        }
        self.metrics: LatencyTracker
        self._speech_started_offsets: dict[str, int]
        self._speech_stopped_events: dict[str, SpeechEvent]
        self._latest_final_transcript_at: float | None
        self._reset_metrics()

    async def stop(self, session_id: str) -> None:
        self._stop_requested.set()
        await self.audio.stop_bot_audio()
        await self.meet.leave()

    async def run(self, session_id: str) -> None:
        self._stop_requested.clear()
        self._reset_metrics()
        consented = False
        recording_started = False
        speech_events: SpeechEventCursor | None = None
        transcript: list[Utterance] = []
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
            plan = await self._timed_llm(
                "prepare",
                self.interviewer.prepare(
                    resume_text=resume_text,
                    job_description_text=job_text,
                    duration_minutes=session.duration_minutes,
                ),
            )

            self._raise_if_stopped()
            await self.repository.transition(session_id, SessionState.JOINING)
            join_outcome = await self.meet.join(session.meeting_url)
            if join_outcome is JoinOutcome.ADMISSION_REQUESTED:
                await self.repository.transition(session_id, SessionState.AWAITING_ADMISSION)
                await self.meet.wait_for_admission(self.admission_timeout_seconds)
            await self.repository.transition(session_id, SessionState.WAITING_FOR_PARTICIPANT)
            await self.meet.wait_for_participant(self.participant_timeout_seconds)
            await self.repository.transition(session_id, SessionState.AWAITING_CONSENT)

            transcription_hints = build_transcription_hints(
                resume_text=resume_text,
                job_description_text=job_text,
                max_chars=self.stt_context_max_chars,
                keyword_limit=self.stt_keyword_limit,
            )
            speech_events = SpeechEventCursor(
                self.stt.transcribe(
                    self.audio.candidate_audio(),
                    hints=transcription_hints,
                )
            )
            consent_text = await self._obtain_consent(speech_events)
            decision = classify_consent(consent_text)
            if decision is not ConsentDecision.GRANTED:
                await self.artifacts.delete_content(session_id)
                with suppress(Exception):
                    await self._play_with_timeout(CONSENT_DECLINED_CLOSING)
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
            await self._conduct_interview(
                session,
                plan,
                speech_events,
                consent_text,
                transcript,
            )
            await self.repository.transition(session_id, SessionState.FINALIZING)
            await self.audio.stop_recording()
            recording_started = False
            notes = await self._timed_llm("notes", self.interviewer.notes(transcript))
            session = await self.repository.get(session_id)
            if session is None:
                return
            await self.artifacts.write_outputs(session, transcript, notes, self.metrics.report())
            await self.repository.transition(session_id, SessionState.COMPLETED)
            completed = await self.repository.get(session_id)
            if completed is not None:
                await self.artifacts.write_outputs(
                    completed,
                    transcript,
                    notes,
                    self.metrics.report(),
                )
        except asyncio.CancelledError:
            await self._stop_session(session_id)
            raise
        except ConsentWithdrawnError:
            if recording_started:
                with suppress(Exception):
                    await self.audio.stop_recording()
                recording_started = False
            await self.artifacts.delete_content(session_id)
            with suppress(Exception):
                await self._play_with_timeout(CONSENT_WITHDRAWAL_CLOSING)
            await self.repository.transition(
                session_id,
                SessionState.STOPPED,
                detail="Candidate withdrew recording consent",
            )
        except ParticipantLeftError:
            if recording_started:
                with suppress(Exception):
                    await self.audio.stop_recording()
                recording_started = False
            stopped = await self.repository.transition(
                session_id,
                SessionState.STOPPED,
                detail="Candidate left the meeting",
            )
            if transcript:
                try:
                    notes = await self._timed_llm("notes", self.interviewer.notes(transcript))
                except Exception:
                    notes = InterviewNotes(
                        summary="The interview ended when the candidate left the meeting.",
                        strengths_observed=[],
                        areas_to_probe=["The interview ended before completion."],
                        evidence=[],
                    )
                with suppress(Exception):
                    await self.artifacts.write_outputs(
                        stopped,
                        transcript,
                        notes,
                        self.metrics.report(),
                    )
        except InterviewerError as exc:
            await self.repository.fail(session_id, exc.code, exc.detail)
        except TimeoutError as exc:
            code = FailureCode.CONSENT_TIMEOUT if not consented else FailureCode.INTERNAL_ERROR
            await self.repository.fail(session_id, code, str(exc))
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"[:500]
            await self.repository.fail(session_id, FailureCode.INTERNAL_ERROR, detail)
        finally:
            if speech_events is not None:
                with suppress(Exception):
                    await speech_events.close()
            if recording_started:
                with suppress(Exception):
                    await self.audio.stop_recording()
            with suppress(Exception):
                await self.meet.leave()

    async def _obtain_consent(self, events: SpeechEventCursor) -> str:
        prompt = CONSENT_DISCLOSURE
        response = ""
        for attempt in range(2):
            response = await self._say_and_receive(
                prompt,
                events,
                timeout_seconds=self.consent_timeout_seconds,
                phase="consent",
            )
            decision = classify_consent(response)
            if decision is not ConsentDecision.UNCLEAR:
                return response
            if attempt == 0:
                prompt = (
                    "Sorry, I need a clear yes or no before we continue. Is it okay if I record "
                    "this interview and create a transcript?"
                )
        return response

    async def _conduct_interview(
        self,
        session: Session,
        plan: str,
        events: SpeechEventCursor,
        consent_text: str,
        transcript: list[Utterance],
    ) -> None:
        duration_minutes = session.duration_minutes
        transcript.extend(
            [
                Utterance(Speaker.INTERVIEWER, CONSENT_DISCLOSURE, 0, 0),
                Utterance(Speaker.CANDIDATE, consent_text, 0, 0),
            ]
        )
        started = time.monotonic()
        duration_seconds = duration_minutes * 60
        opening = interview_opening()
        opening_started = int((time.monotonic() - started) * 1000)
        transcript.append(Utterance(Speaker.INTERVIEWER, opening, opening_started, opening_started))
        opening_response = await self._say_and_receive(
            opening,
            events,
            timeout_seconds=self.response_timeout_seconds,
            phase="opening",
        )
        opening_ended = int((time.monotonic() - started) * 1000)
        (
            opening_response,
            opening_response_started,
            opening_ended,
        ) = await self._honor_repeat_requests(
            response=opening_response,
            prompt=opening,
            events=events,
            transcript=transcript,
            interview_started=started,
            response_started=opening_started,
            response_ended=opening_ended,
        )
        self._raise_if_consent_withdrawn(opening_response)
        transcript.append(
            Utterance(
                Speaker.CANDIDATE,
                opening_response,
                opening_response_started,
                opening_ended,
            )
        )
        if is_interview_end_request(opening_response):
            await self._close_interview(transcript, started)
            return
        for _ in range(self.transcript_clarification_attempts):
            if not transcript_needs_clarification(opening_response):
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
            opening_response = await self._say_and_receive(
                clarification,
                events,
                timeout_seconds=self.response_timeout_seconds,
                phase="clarification",
            )
            opening_ended = int((time.monotonic() - started) * 1000)
            opening_response, response_started, opening_ended = await self._honor_repeat_requests(
                response=opening_response,
                prompt=clarification,
                events=events,
                transcript=transcript,
                interview_started=started,
                response_started=clarification_started,
                response_ended=opening_ended,
            )
            self._raise_if_consent_withdrawn(opening_response)
            transcript.append(
                Utterance(
                    Speaker.CANDIDATE,
                    opening_response,
                    response_started,
                    opening_ended,
                )
            )
        if is_interview_end_request(opening_response):
            await self._close_interview(transcript, started)
            return
        time_limit_closing = False
        while not self._stop_requested.is_set():
            elapsed = int(time.monotonic() - started)
            remaining = max(0, duration_seconds - elapsed)
            if remaining <= INTERVIEW_CLOSING_RESERVE_SECONDS:
                time_limit_closing = True
                break
            final_question = remaining <= INTERVIEW_FINAL_QUESTION_WINDOW_SECONDS
            turn = await self._timed_llm(
                "next_turn",
                self.interviewer.next_turn(
                    plan=plan,
                    transcript=transcript,
                    seconds_remaining=remaining,
                ),
            )
            remaining_after_generation = duration_seconds - int(time.monotonic() - started)
            if turn.should_end:
                time_limit_closing = final_question
                break
            if remaining_after_generation <= INTERVIEW_CLOSING_RESERVE_SECONDS:
                time_limit_closing = True
                break
            spoken_turn = final_question_prompt(turn.say) if final_question else turn.say
            turn_started = int((time.monotonic() - started) * 1000)
            transcript.append(
                Utterance(Speaker.INTERVIEWER, spoken_turn, turn_started, turn_started)
            )
            response = await self._say_and_receive(
                spoken_turn,
                events,
                timeout_seconds=self.response_timeout_seconds,
                phase="interview",
            )
            response_ended = int((time.monotonic() - started) * 1000)
            response, response_started, response_ended = await self._honor_repeat_requests(
                response=response,
                prompt=spoken_turn,
                events=events,
                transcript=transcript,
                interview_started=started,
                response_started=turn_started,
                response_ended=response_ended,
            )
            self._raise_if_consent_withdrawn(response)
            transcript.append(
                Utterance(Speaker.CANDIDATE, response, response_started, response_ended)
            )
            if is_interview_end_request(response):
                break
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
                    phase="clarification",
                )
                response_ended = int((time.monotonic() - started) * 1000)
                response, response_started, response_ended = await self._honor_repeat_requests(
                    response=response,
                    prompt=clarification,
                    events=events,
                    transcript=transcript,
                    interview_started=started,
                    response_started=clarification_started,
                    response_ended=response_ended,
                )
                self._raise_if_consent_withdrawn(response)
                transcript.append(
                    Utterance(
                        Speaker.CANDIDATE,
                        response,
                        response_started,
                        response_ended,
                    )
                )
            if is_interview_end_request(response):
                break
            if final_question:
                time_limit_closing = True
                break
        closing_text = TIME_LIMIT_CLOSING if time_limit_closing else INTERVIEW_CLOSING
        await self._close_interview(transcript, started, closing_text=closing_text)

    async def _close_interview(
        self,
        transcript: list[Utterance],
        interview_started: float,
        *,
        closing_text: str = INTERVIEW_CLOSING,
    ) -> None:
        closing_started = int((time.monotonic() - interview_started) * 1000)
        transcript.append(
            Utterance(Speaker.INTERVIEWER, closing_text, closing_started, closing_started)
        )
        await self._play_with_timeout(closing_text, phase="closing")
        self._raise_if_stopped()

    async def _honor_repeat_requests(
        self,
        *,
        response: str,
        prompt: str,
        events: SpeechEventCursor,
        transcript: list[Utterance],
        interview_started: float,
        response_started: int,
        response_ended: int,
    ) -> tuple[str, int, int]:
        for _ in range(2):
            if not is_repeat_request(response):
                break
            self._raise_if_consent_withdrawn(response)
            transcript.append(
                Utterance(Speaker.CANDIDATE, response, response_started, response_ended)
            )
            repeated = repeat_prompt(prompt)
            repeated_started = int((time.monotonic() - interview_started) * 1000)
            transcript.append(
                Utterance(
                    Speaker.INTERVIEWER,
                    repeated,
                    repeated_started,
                    repeated_started,
                )
            )
            response = await self._say_and_receive(
                repeated,
                events,
                timeout_seconds=self.response_timeout_seconds,
                phase="repeat",
            )
            response_started = repeated_started
            response_ended = int((time.monotonic() - interview_started) * 1000)
        return response, response_started, response_ended

    async def _say_and_receive(
        self,
        text: str,
        events: SpeechEventCursor | AsyncIterator[SpeechEvent],
        *,
        timeout_seconds: float,
        phase: str = "interview",
    ) -> str:
        cursor = events if isinstance(events, SpeechEventCursor) else SpeechEventCursor(events)
        owns_cursor = cursor is not events
        playback = asyncio.create_task(self._play_measured(text, phase=phase))
        playback_deadline = time.monotonic() + self.tts_timeout_seconds
        response_deadline: float | None = None
        completion_deadline: float | None = None
        transcript_fragments: list[str] = []
        speech_active = False
        active_item_id: str | None = None
        try:
            while True:
                self._raise_if_stopped()
                if playback.done() and response_deadline is None:
                    if not playback.cancelled():
                        playback.result()
                    response_deadline = time.monotonic() + timeout_seconds
                event_task = cursor.next_task()
                waiting: set[asyncio.Task[object]] = {event_task}
                if response_deadline is None:
                    waiting.add(playback)
                deadline = response_deadline or playback_deadline
                if completion_deadline is not None:
                    deadline = min(deadline, completion_deadline)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if transcript_fragments and completion_deadline is not None:
                        return " ".join(transcript_fragments)
                    if response_deadline is None:
                        raise TimeoutError("Timed out playing interviewer speech")
                    await self._raise_if_participant_left()
                    raise TimeoutError("Timed out waiting for candidate speech")
                done, _ = await asyncio.wait(
                    waiting,
                    timeout=remaining,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    if transcript_fragments and completion_deadline is not None:
                        return " ".join(transcript_fragments)
                    if response_deadline is None:
                        raise TimeoutError("Timed out playing interviewer speech")
                    await self._raise_if_participant_left()
                    raise TimeoutError("Timed out waiting for candidate speech")
                if event_task in done:
                    event = cursor.consume(event_task)
                    self._record_stt_event(event, phase=phase)
                    if event.kind is SpeechEventKind.SPEECH_STARTED:
                        if not playback.done():
                            await self._stop_playback(playback)
                        speech_active = True
                        active_item_id = event.item_id
                        response_deadline = time.monotonic() + self.candidate_turn_timeout_seconds
                        completion_deadline = None
                    elif event.kind is SpeechEventKind.SPEECH_STOPPED:
                        continue
                    elif event.kind is SpeechEventKind.FINAL_TRANSCRIPT:
                        if not playback.done():
                            await self._stop_playback(playback)
                        if not transcript_fragments or transcript_fragments[-1] != event.text:
                            transcript_fragments.append(event.text)
                        if is_thinking_request(" ".join(transcript_fragments)):
                            speech_active = False
                            active_item_id = None
                            response_deadline = (
                                time.monotonic() + self.candidate_turn_timeout_seconds
                            )
                            completion_deadline = None
                            continue
                        closes_active_item = (
                            not speech_active
                            or active_item_id is None
                            or event.item_id is None
                            or event.item_id == active_item_id
                        )
                        if closes_active_item:
                            speech_active = False
                            active_item_id = None
                            completion_deadline = (
                                time.monotonic() + self.candidate_turn_grace_seconds
                            )
                if playback in done:
                    if not playback.cancelled():
                        playback.result()
                    if response_deadline is None:
                        response_deadline = time.monotonic() + timeout_seconds
        finally:
            if not playback.done():
                await self.audio.stop_bot_audio()
                playback.cancel()
            with suppress(asyncio.CancelledError):
                await playback
            if owns_cursor:
                await cursor.close()

    async def _stop_playback(self, playback: asyncio.Task[None]) -> None:
        await self.audio.stop_bot_audio()
        if not playback.done():
            playback.cancel()
        with suppress(asyncio.CancelledError):
            await playback

    async def _play_with_timeout(self, text: str, *, phase: str = "closing") -> None:
        try:
            async with asyncio.timeout(self.tts_timeout_seconds):
                await self._play_measured(text, phase=phase)
        except TimeoutError as exc:
            await self.audio.stop_bot_audio()
            raise TimeoutError("Timed out playing interviewer speech") from exc

    async def _play_measured(self, text: str, *, phase: str) -> None:
        playback_started = time.monotonic()
        synthesis_started = playback_started
        response_anchor = self._latest_final_transcript_at
        first_audio_at: float | None = None
        status = "completed"

        async def measured_audio() -> AsyncIterator[bytes]:
            nonlocal first_audio_at
            async for chunk in self.tts.synthesize(text):
                if first_audio_at is None:
                    first_audio_at = time.monotonic()
                    self.metrics.record(
                        "tts.first_audio",
                        first_audio_at - synthesis_started,
                        phase=phase,
                    )
                    if response_anchor is not None:
                        self.metrics.record(
                            "pipeline.response_to_first_audio",
                            first_audio_at - response_anchor,
                            phase=phase,
                        )
                        if self._latest_final_transcript_at == response_anchor:
                            self._latest_final_transcript_at = None
                yield chunk

        try:
            await self.audio.play_bot_audio(measured_audio())
        except asyncio.CancelledError:
            status = "interrupted"
            raise
        except Exception:
            status = "failed"
            raise
        finally:
            playback_ended = time.monotonic()
            self.metrics.record(
                "tts.playback",
                playback_ended - playback_started,
                phase=phase,
                status=status,
            )
            if response_anchor is not None and first_audio_at is not None:
                self.metrics.record(
                    "pipeline.response_to_playback_end",
                    playback_ended - response_anchor,
                    phase=phase,
                    status=status,
                )

    async def _timed_llm(self, operation: str, awaitable: Awaitable[T]) -> T:
        started = time.monotonic()
        status = "completed"
        try:
            return await awaitable
        except Exception:
            status = "failed"
            raise
        finally:
            phase = {
                "prepare": "preparation",
                "notes": "finalization",
            }.get(operation, "interview")
            self.metrics.record(
                "llm.request",
                time.monotonic() - started,
                phase=phase,
                operation=operation,
                status=status,
            )

    def _record_stt_event(self, event: SpeechEvent, *, phase: str) -> None:
        item_id = event.item_id
        if event.kind is SpeechEventKind.SPEECH_STARTED:
            if item_id is not None and event.audio_offset_ms is not None:
                self._speech_started_offsets[item_id] = event.audio_offset_ms
            return
        if event.kind is SpeechEventKind.SPEECH_STOPPED:
            if item_id is not None:
                self._speech_stopped_events[item_id] = event
            return
        if event.kind is not SpeechEventKind.FINAL_TRANSCRIPT:
            return

        self._latest_final_transcript_at = event.received_at_monotonic
        if item_id is None:
            return
        stopped = self._speech_stopped_events.pop(item_id, None)
        started_offset = self._speech_started_offsets.pop(item_id, None)
        if stopped is None:
            return
        if (
            started_offset is not None
            and stopped.audio_offset_ms is not None
            and stopped.audio_offset_ms >= started_offset
        ):
            self.metrics.record(
                "stt.audio_segment",
                (stopped.audio_offset_ms - started_offset) / 1000,
                phase=phase,
                item_id=item_id,
            )
        self.metrics.record(
            "stt.post_speech",
            event.received_at_monotonic - stopped.received_at_monotonic,
            phase=phase,
            item_id=item_id,
        )

    def _reset_metrics(self) -> None:
        self.metrics = LatencyTracker(models=self._metric_models)
        self._speech_started_offsets = {}
        self._speech_stopped_events = {}
        self._latest_final_transcript_at = None

    @staticmethod
    def _raise_if_consent_withdrawn(response: str) -> None:
        if is_consent_withdrawal(response):
            raise ConsentWithdrawnError

    def _raise_if_stopped(self) -> None:
        if self._stop_requested.is_set():
            raise asyncio.CancelledError

    async def _raise_if_participant_left(self) -> None:
        if not await self.meet.participant_present():
            raise ParticipantLeftError

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
