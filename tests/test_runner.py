import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from tests.fakes import FakeAudio, FakeInterviewer, FakeMeet, FakeSTT, FakeTTS
from voice_interviewer.artifacts import FilesystemArtifactStore
from voice_interviewer.domain import Session, SessionState, SpeechEvent, SpeechEventKind
from voice_interviewer.persistence import SqlAlchemySessionRepository
from voice_interviewer.runner import ConversationRunner


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
    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=audio,
        stt=FakeSTT(
            [
                SpeechEvent(SpeechEventKind.SPEECH_STARTED),
                SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "Yes, I consent"),
                SpeechEvent(SpeechEventKind.SPEECH_STARTED),
                SpeechEvent(
                    SpeechEventKind.FINAL_TRANSCRIPT,
                    "I designed a versioned FastAPI service.",
                ),
            ]
        ),
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
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
    assert audio.stops >= 2
    names = {path.name for path in await artifacts.list(str(session.id))}
    assert names == {
        "interview.mp3",
        "notes.md",
        "session.json",
        "transcript.json",
        "transcript.md",
    }
    await repository.close()


async def test_runner_deletes_content_when_consent_declined(tmp_path: Path) -> None:
    session, repository, artifacts = await prepare(tmp_path)
    runner = ConversationRunner(
        repository=repository,
        artifacts=artifacts,
        meet=FakeMeet(),
        audio=FakeAudio(),
        stt=FakeSTT([SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, "No, I decline")]),
        interviewer=FakeInterviewer(),
        tts=FakeTTS(),
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
    await repository.close()


async def test_runner_deletes_content_when_consent_is_withdrawn(tmp_path: Path) -> None:
    session, repository, artifacts = await prepare(tmp_path)
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
        tts=FakeTTS(),
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
