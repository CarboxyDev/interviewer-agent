from pathlib import Path

import pytest

from voice_interviewer.domain import FailureCode, Session, SessionState
from voice_interviewer.errors import InvalidTransitionError
from voice_interviewer.persistence import SqlAlchemySessionRepository


def database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"


async def test_repository_enforces_transitions_and_active_state(tmp_path: Path) -> None:
    repository = SqlAlchemySessionRepository(database_url(tmp_path))
    await repository.initialize()
    session = Session(
        meeting_url="https://meet.google.com/abc-defg-hij",
        duration_minutes=15,
        resume_name="resume.txt",
        job_description_name="job.txt",
    )
    await repository.create(session)
    assert await repository.has_active()
    assert (await repository.get(str(session.id))).state is SessionState.CREATED  # type: ignore[union-attr]

    with pytest.raises(InvalidTransitionError):
        await repository.transition(str(session.id), SessionState.ACTIVE)

    await repository.transition(str(session.id), SessionState.PREPARING)
    consented = await repository.set_consent(str(session.id))
    assert consented.consented_at is not None
    failed = await repository.fail(str(session.id), FailureCode.INTERNAL_ERROR, "failure")
    assert failed.state is SessionState.FAILED
    assert failed.failure_code is FailureCode.INTERNAL_ERROR
    assert not await repository.has_active()
    assert await repository.delete(str(session.id))
    assert await repository.get(str(session.id)) is None
    await repository.close()


async def test_restart_marks_nonterminal_sessions_failed(tmp_path: Path) -> None:
    repository = SqlAlchemySessionRepository(database_url(tmp_path))
    await repository.initialize()
    session = Session(
        meeting_url="https://meet.google.com/abc-defg-hij",
        duration_minutes=15,
        resume_name="resume.txt",
        job_description_name="job.txt",
    )
    await repository.create(session)
    assert await repository.fail_interrupted() == 1
    interrupted = await repository.get(str(session.id))
    assert interrupted is not None
    assert interrupted.state is SessionState.FAILED
    assert interrupted.failure_detail == "Service restarted during the interview"
    await repository.close()
