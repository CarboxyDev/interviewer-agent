import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from tests.fakes import FakeAudio, FakeInterviewer, FakeMeet, FakeSTT, FakeTTS
from voice_interviewer.artifacts import FilesystemArtifactStore
from voice_interviewer.conversation import (
    CONSENT_DECLINED_CLOSING,
    CONSENT_WITHDRAWAL_CLOSING,
    INTERVIEW_CLOSING,
    TIME_LIMIT_CLOSING,
    interview_opening,
)
from voice_interviewer.domain import (
    JoinOutcome,
    Session,
    SessionState,
    SpeechEvent,
    SpeechEventKind,
)
from voice_interviewer.persistence import SqlAlchemySessionRepository
from voice_interviewer.runner import ConversationRunner, SpeechEventCursor


async def prepare(
    tmp_path: Path,
) -> tuple[
    Session,
    SqlAlchemySessionRepository,
    FilesystemArtifactStore,
]:
    repository = SqlAlchemySessionRepository(f"sqlite+aiosqlite:///{tmp_path / 'runner.db'}")
    await repository.initialize()
    artifacts = FilesystemArtifactStore(tmp_path / "sessions")
    session = Session(
        meeting_url="https://meet.google.com/abc-defg-hij",
        duration_minutes=5,
        resume_name="resume.txt",
        job_description_name="job.txt",
    )
    await artifacts.prepare_inputs(
        str(session.id),
        resume_name=session.resume_name,
        resume=b"Python engineer who designed APIs",
        job_description_name=session.job_description_name,
        job_description=b"Backend engineer building APIs",
    )
    await repository.create(session)
    return session, repository, artifacts


async def test_runner_completes_consented_interview_with_barge_in(tmp_path: Path) -> None:
    session, repository, artifacts = await prepare(tmp_path)
    audio = FakeAudio()
    meet = FakeMeet(JoinOutcome.ADMISSION_REQUESTED)
    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=meet,
        audio=audio,
        stt=FakeSTT(
            [
                SpeechEvent(
                    SpeechEventKind.SPEECH_STARTED,
                    item_id="consent-1",
                    audio_offset_ms=100,
                ),
                SpeechEvent(
                    SpeechEventKind.SPEECH_STOPPED,
                    item_id="consent-1",
                    audio_offset_ms=800,
                ),
                SpeechEvent(
                    SpeechEventKind.FINAL_TRANSCRIPT,
                    "Yes, I consent",
                    item_id="consent-1",
                ),
                SpeechEvent(SpeechEventKind.SPEECH_STARTED),
                SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Let me think"),
                SpeechEvent(SpeechEventKind.SPEECH_STARTED),
                SpeechEvent(
                    SpeechEventKind.FINAL_TRANSCRIPT,
                    "I currently build backend APIs and data pipelines.",
                ),
                SpeechEvent(SpeechEventKind.SPEECH_STARTED),
                SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Sorry, can you repeat?"),
                SpeechEvent(SpeechEventKind.SPEECH_STARTED),
                SpeechEvent(
                    SpeechEventKind.FINAL_TRANSCRIPT,
                    "I designed a versioned FastAPI service.",
                ),
            ]
        ),
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=1,
        candidate_turn_timeout_seconds=1,
        candidate_turn_grace_seconds=0,
        tts_timeout_seconds=1,
        stt_context_max_chars=500,
        stt_keyword_limit=20,
        transcript_clarification_attempts=1,
    )
    await runner.run(str(session.id))

    completed = await repository.get(str(session.id))
    assert completed is not None
    assert completed.state is SessionState.COMPLETED
    assert completed.consented_at is not None
    assert meet.admission_waited is True
    assert audio.stops >= 2
    transcript_path = artifacts.session_dir(str(session.id)) / "transcript.json"
    utterances = json.loads(transcript_path.read_text())
    assert utterances[2]["text"] == interview_opening(5)
    assert utterances[3]["text"] == (
        "Let me think I currently build backend APIs and data pipelines."
    )
    assert any(
        item["text"] == "Of course. Tell me about an API you designed." for item in utterances
    )
    assert utterances[-1]["text"] == INTERVIEW_CLOSING
    assert not any(
        item["text"] == "What if the external call succeeded but the database write failed?"
        for item in utterances
    )
    metrics = json.loads((artifacts.session_dir(str(session.id)) / "metrics.json").read_text())
    assert metrics["summary"]["llm.request.next_turn"]["count"] == 2
    assert metrics["summary"]["stt.audio_segment"]["average_ms"] == 700.0
    assert metrics["summary"]["stt.post_speech"]["count"] == 1
    assert metrics["summary"]["tts.first_audio"]["count"] >= 1
    assert metrics["summary"]["pipeline.response_to_first_audio"]["count"] >= 1
    names = {path.name for path in await artifacts.list(str(session.id))}
    assert names == {
        "interview.mp3",
        "metrics.json",
        "notes.md",
        "session.json",
        "transcript.json",
        "transcript.md",
    }
    await repository.close()


async def test_runner_deletes_content_when_consent_declined(tmp_path: Path) -> None:
    session, repository, artifacts = await prepare(tmp_path)
    tts = FakeTTS()
    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=FakeSTT([SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "No, I decline")]),
        interviewer=FakeInterviewer(),
        tts=tts,
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=1,
        candidate_turn_timeout_seconds=1,
        candidate_turn_grace_seconds=0,
        tts_timeout_seconds=1,
        stt_context_max_chars=500,
        stt_keyword_limit=20,
        transcript_clarification_attempts=1,
    )
    await runner.run(str(session.id))
    declined = await repository.get(str(session.id))
    assert declined is not None
    assert declined.state is SessionState.STOPPED
    assert declined.consented_at is None
    assert not artifacts.session_dir(str(session.id)).exists()
    assert tts.spoken[-1] == CONSENT_DECLINED_CLOSING
    await repository.close()


async def test_runner_deletes_content_when_consent_is_withdrawn(tmp_path: Path) -> None:
    session, repository, artifacts = await prepare(tmp_path)
    tts = FakeTTS()
    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=FakeSTT(
            [
                SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Yes, I consent"),
                SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Please stop the recording"),
            ]
        ),
        interviewer=FakeInterviewer(),
        tts=tts,
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=1,
        candidate_turn_timeout_seconds=1,
        candidate_turn_grace_seconds=0,
        tts_timeout_seconds=1,
        stt_context_max_chars=500,
        stt_keyword_limit=20,
        transcript_clarification_attempts=1,
    )
    await runner.run(str(session.id))
    withdrawn = await repository.get(str(session.id))
    assert withdrawn is not None
    assert withdrawn.state is SessionState.STOPPED
    assert not artifacts.session_dir(str(session.id)).exists()
    assert tts.spoken[-1] == CONSENT_WITHDRAWAL_CLOSING
    await repository.close()


async def test_runner_ends_interview_and_keeps_outputs_when_candidate_asks_to_stop(
    tmp_path: Path,
) -> None:
    session, repository, artifacts = await prepare(tmp_path)
    tts = FakeTTS()
    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=FakeSTT(
            [
                SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Yes, I consent"),
                SpeechEvent(
                    SpeechEventKind.FINAL_TRANSCRIPT,
                    "I recently worked on backend invoice workflows.",
                ),
                SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Please stop the interview"),
            ]
        ),
        interviewer=FakeInterviewer(),
        tts=tts,
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=1,
        candidate_turn_timeout_seconds=1,
        candidate_turn_grace_seconds=0,
        tts_timeout_seconds=1,
        stt_context_max_chars=500,
        stt_keyword_limit=20,
        transcript_clarification_attempts=1,
    )

    await runner.run(str(session.id))

    completed = await repository.get(str(session.id))
    assert completed is not None
    assert completed.state is SessionState.COMPLETED
    names = {path.name for path in await artifacts.list(str(session.id))}
    assert names == {
        "interview.mp3",
        "metrics.json",
        "notes.md",
        "session.json",
        "transcript.json",
        "transcript.md",
    }
    transcript = json.loads(
        (artifacts.session_dir(str(session.id)) / "transcript.json").read_text()
    )
    assert transcript[-2]["text"] == "Please stop the interview"
    assert transcript[-1]["text"] == INTERVIEW_CLOSING
    assert tts.spoken[-1] == INTERVIEW_CLOSING
    await repository.close()


async def test_runner_announces_one_final_question_then_uses_time_closing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "voice_interviewer.runner.INTERVIEW_FINAL_QUESTION_WINDOW_SECONDS",
        600,
    )
    monkeypatch.setattr(
        "voice_interviewer.runner.INTERVIEW_CLOSING_RESERVE_SECONDS",
        0,
    )
    session, repository, artifacts = await prepare(tmp_path)
    tts = FakeTTS()
    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=FakeSTT(
            [
                SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Yes, I consent"),
                SpeechEvent(
                    SpeechEventKind.FINAL_TRANSCRIPT,
                    "I recently worked on backend invoice workflows.",
                ),
                SpeechEvent(
                    SpeechEventKind.FINAL_TRANSCRIPT,
                    "I designed a versioned API.",
                ),
            ]
        ),
        interviewer=FakeInterviewer(),
        tts=tts,
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=1,
        candidate_turn_timeout_seconds=1,
        candidate_turn_grace_seconds=0,
        tts_timeout_seconds=1,
        stt_context_max_chars=500,
        stt_keyword_limit=20,
        transcript_clarification_attempts=1,
    )

    await runner.run(str(session.id))

    transcript = json.loads(
        (artifacts.session_dir(str(session.id)) / "transcript.json").read_text()
    )
    questions = [
        item["text"]
        for item in transcript
        if item["speaker"] == "interviewer" and "?" in item["text"]
    ]
    assert questions[-1].startswith("We are nearly out of time, so one final question.")
    assert transcript[-1]["text"] == TIME_LIMIT_CLOSING
    assert tts.spoken[-1] == TIME_LIMIT_CLOSING
    metrics = json.loads((artifacts.session_dir(str(session.id)) / "metrics.json").read_text())
    assert metrics["summary"]["llm.request.next_turn"]["count"] == 1
    await repository.close()


async def test_runner_stops_gracefully_and_keeps_partial_outputs_when_candidate_leaves(
    tmp_path: Path,
) -> None:
    session, repository, artifacts = await prepare(tmp_path)
    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(participant_present=False),
        audio=FakeAudio(),
        stt=FakeSTT(
            [SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Yeah, go ahead")],
            hold_open=True,
        ),
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=0,
        candidate_turn_timeout_seconds=1,
        candidate_turn_grace_seconds=0,
        tts_timeout_seconds=1,
        stt_context_max_chars=500,
        stt_keyword_limit=20,
        transcript_clarification_attempts=1,
    )

    await runner.run(str(session.id))

    stopped = await repository.get(str(session.id))
    assert stopped is not None
    assert stopped.state is SessionState.STOPPED
    names = {path.name for path in await artifacts.list(str(session.id))}
    assert names == {
        "interview.mp3",
        "metrics.json",
        "notes.md",
        "session.json",
        "transcript.json",
        "transcript.md",
    }
    await repository.close()


async def test_runner_retries_an_unclear_transcript_and_passes_stt_hints(tmp_path: Path) -> None:
    session, repository, artifacts = await prepare(tmp_path)
    stt = FakeSTT(
        [
            SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Yes, I consent"),
            SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "[inaudible]"),
            SpeechEvent(
                SpeechEventKind.FINAL_TRANSCRIPT,
                "I designed a versioned FastAPI service.",
            ),
        ]
    )
    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=stt,
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=1,
        candidate_turn_timeout_seconds=1,
        candidate_turn_grace_seconds=0,
        tts_timeout_seconds=1,
        stt_context_max_chars=500,
        stt_keyword_limit=20,
        transcript_clarification_attempts=1,
    )

    await runner.run(str(session.id))

    completed = await repository.get(str(session.id))
    assert completed is not None
    assert completed.state is SessionState.COMPLETED
    assert stt.hints is not None
    assert "APIs" in stt.hints.keywords
    assert "Python engineer" in stt.hints.prompt
    transcript_path = artifacts.session_dir(str(session.id)) / "transcript.json"
    utterances = json.loads(transcript_path.read_text())
    assert any("repeat your answer" in item["text"] for item in utterances)
    assert utterances[-2]["text"] == "I designed a versioned FastAPI service."
    await repository.close()


async def test_response_timeout_starts_after_playback_finishes(tmp_path: Path) -> None:
    _session, repository, artifacts = await prepare(tmp_path)

    class DelayedAudio(FakeAudio):
        async def play_bot_audio(self, audio: AsyncIterator[bytes]) -> None:
            await asyncio.sleep(0.1)
            async for _ in audio:
                pass

    async def delayed_final() -> AsyncIterator[SpeechEvent]:
        await asyncio.sleep(0.15)
        yield SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "A complete answer")

    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=DelayedAudio(),
        stt=FakeSTT([]),
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=1,
        candidate_turn_timeout_seconds=1,
        candidate_turn_grace_seconds=0,
        tts_timeout_seconds=1,
        stt_context_max_chars=0,
        stt_keyword_limit=0,
        transcript_clarification_attempts=0,
    )

    response = await runner._say_and_receive(
        "Tell me about your work.",
        delayed_final(),
        timeout_seconds=0.1,
    )

    assert response == "A complete answer"
    await repository.close()


async def test_pending_stt_read_is_reused_across_consecutive_turns(tmp_path: Path) -> None:
    _session, repository, artifacts = await prepare(tmp_path)

    async def consecutive_answers() -> AsyncIterator[SpeechEvent]:
        yield SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Yes, I consent")
        await asyncio.sleep(0.08)
        yield SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "My backend answer")
        await asyncio.Event().wait()

    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=FakeSTT([]),
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=0.2,
        candidate_turn_timeout_seconds=1,
        candidate_turn_grace_seconds=0.02,
        tts_timeout_seconds=1,
        stt_context_max_chars=0,
        stt_keyword_limit=0,
        transcript_clarification_attempts=0,
    )
    cursor = SpeechEventCursor(consecutive_answers())
    try:
        consent = await runner._say_and_receive(
            "Do you consent?",
            cursor,
            timeout_seconds=0.2,
        )
        answer = await runner._say_and_receive(
            "Tell me about your backend work.",
            cursor,
            timeout_seconds=0.2,
        )
    finally:
        await cursor.close()

    assert consent == "Yes, I consent"
    assert answer == "My backend answer"
    await repository.close()


async def test_active_candidate_speech_uses_longer_turn_timeout(tmp_path: Path) -> None:
    _session, repository, artifacts = await prepare(tmp_path)

    async def long_answer() -> AsyncIterator[SpeechEvent]:
        await asyncio.sleep(0.02)
        yield SpeechEvent(SpeechEventKind.SPEECH_STARTED)
        await asyncio.sleep(0.12)
        yield SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "A complete long answer")

    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=FakeSTT([]),
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=0.05,
        candidate_turn_timeout_seconds=0.3,
        candidate_turn_grace_seconds=0,
        tts_timeout_seconds=1,
        stt_context_max_chars=0,
        stt_keyword_limit=0,
        transcript_clarification_attempts=0,
    )

    response = await runner._say_and_receive(
        "Tell me about your work.",
        long_answer(),
        timeout_seconds=0.05,
    )

    assert response == "A complete long answer"
    await repository.close()


async def test_adjacent_stt_segments_are_combined_into_one_answer(tmp_path: Path) -> None:
    _session, repository, artifacts = await prepare(tmp_path)

    async def segmented_answer() -> AsyncIterator[SpeechEvent]:
        await asyncio.sleep(0.02)
        yield SpeechEvent(SpeechEventKind.SPEECH_STARTED)
        await asyncio.sleep(0.01)
        yield SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "First sentence.")
        await asyncio.sleep(0.02)
        yield SpeechEvent(SpeechEventKind.SPEECH_STARTED)
        await asyncio.sleep(0.01)
        yield SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Second sentence.")
        await asyncio.sleep(0.2)

    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=FakeSTT([]),
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=0.1,
        candidate_turn_timeout_seconds=0.5,
        candidate_turn_grace_seconds=0.05,
        tts_timeout_seconds=1,
        stt_context_max_chars=0,
        stt_keyword_limit=0,
        transcript_clarification_attempts=0,
    )

    response = await runner._say_and_receive(
        "Tell me about your work.",
        segmented_answer(),
        timeout_seconds=0.1,
    )

    assert response == "First sentence. Second sentence."
    await repository.close()


async def test_older_final_event_does_not_close_newer_active_segment(tmp_path: Path) -> None:
    _session, repository, artifacts = await prepare(tmp_path)

    async def reordered_events() -> AsyncIterator[SpeechEvent]:
        yield SpeechEvent(SpeechEventKind.SPEECH_STARTED, item_id="item-1")
        yield SpeechEvent(SpeechEventKind.SPEECH_STARTED, item_id="item-2")
        yield SpeechEvent(
            SpeechEventKind.FINAL_TRANSCRIPT,
            "First sentence.",
            item_id="item-1",
        )
        await asyncio.sleep(0.08)
        yield SpeechEvent(
            SpeechEventKind.FINAL_TRANSCRIPT,
            "Second sentence.",
            item_id="item-2",
        )
        await asyncio.sleep(0.2)

    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=FakeSTT([]),
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
        admission_timeout_seconds=1,
        participant_timeout_seconds=1,
        consent_timeout_seconds=1,
        response_timeout_seconds=0.1,
        candidate_turn_timeout_seconds=0.5,
        candidate_turn_grace_seconds=0.05,
        tts_timeout_seconds=1,
        stt_context_max_chars=0,
        stt_keyword_limit=0,
        transcript_clarification_attempts=0,
    )

    response = await runner._say_and_receive(
        "Tell me about your work.",
        reordered_events(),
        timeout_seconds=0.1,
    )

    assert response == "First sentence. Second sentence."
    await repository.close()
