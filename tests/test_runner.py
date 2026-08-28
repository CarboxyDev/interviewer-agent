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
    )
    await runner.run(str(session.id))
    withdrawn = await repository.get(str(session.id))
    assert withdrawn is not None
    assert withdrawn.state is SessionState.STOPPED
    assert not artifacts.session_dir(str(session.id)).exists()
    await repository.close()
