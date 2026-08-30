from pathlib import Path

import pytest

from tests.fakes import HoldingRunner
from voice_interviewer.artifacts import FilesystemArtifactStore
from voice_interviewer.domain import SessionCreate, SessionState
from voice_interviewer.errors import ActiveSessionError, DocumentError, SessionNotFoundError
from voice_interviewer.persistence import SqlAlchemySessionRepository
from voice_interviewer.service import InterviewService


async def make_service(tmp_path: Path) -> tuple[InterviewService, SqlAlchemySessionRepository]:
    repository = SqlAlchemySessionRepository(f"sqlite+aiosqlite:///{tmp_path / 'service.db'}")
    await repository.initialize()
    runner = HoldingRunner(repository)
    return (
        InterviewService(
            repository=repository,
            artifacts=FilesystemArtifactStore(tmp_path / "artifacts"),
            runner=runner,
            maximum_upload_bytes=1024,
        ),
        repository,
    )


async def test_service_enforces_single_active_session_and_deletion(tmp_path: Path) -> None:
    service, repository = await make_service(tmp_path)
    request = SessionCreate.model_validate(
        {
            "meeting_url": "https://meet.google.com/abc-defg-hij",
            "duration_minutes": 15,
            "meeting_authorization_confirmed": True,
        }
    )
    created = await service.create(
        request,
        resume_name="resume.txt",
        resume=b"Python backend engineer",
        job_description_name="job.txt",
        job_description=b"Build backend services",
    )
    assert created.state is SessionState.CREATED
    with pytest.raises(ActiveSessionError):
        await service.create(
            request,
            resume_name="resume.txt",
            resume=b"Another resume",
            job_description_name="job.txt",
            job_description=b"Another job",
        )
    stopped = await service.stop(str(created.id))
    assert stopped.state is SessionState.STOPPED
    await service.delete(str(created.id))
    with pytest.raises(SessionNotFoundError):
        await service.get(str(created.id))
    await repository.close()


async def test_service_rejects_bad_documents(tmp_path: Path) -> None:
    service, repository = await make_service(tmp_path)
    request = SessionCreate.model_validate(
        {
            "meeting_url": "https://meet.google.com/abc-defg-hij",
            "meeting_authorization_confirmed": True,
        }
    )
    with pytest.raises(DocumentError, match="PDF, DOCX, or TXT"):
        await service.create(
            request,
            resume_name="resume.md",
            resume=b"resume",
            job_description_name="job.txt",
            job_description=b"job",
        )
    await repository.close()
