from __future__ import annotations

import asyncio
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from voice_interviewer.artifacts import safe_filename
from voice_interviewer.documents import SUPPORTED_EXTENSIONS, extract_document
from voice_interviewer.domain import Session, SessionCreate, SessionState, SessionView
from voice_interviewer.errors import ActiveSessionError, DocumentError, SessionNotFoundError
from voice_interviewer.ports import ArtifactStore, InterviewRunner, SessionRepository


class InterviewService:
    def __init__(
        self,
        *,
        repository: SessionRepository,
        artifacts: ArtifactStore,
        runner: InterviewRunner,
        maximum_upload_bytes: int,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.runner = runner
        self.maximum_upload_bytes = maximum_upload_bytes
        self._create_lock = asyncio.Lock()
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def create(
        self,
        request: SessionCreate,
        *,
        resume_name: str,
        resume: bytes,
        job_description_name: str,
        job_description: bytes,
    ) -> SessionView:
        self._validate_upload(resume_name, resume, "resume")
        self._validate_upload(job_description_name, job_description, "job description")
        async with self._create_lock:
            if await self.repository.has_active():
                raise ActiveSessionError("Only one interview can be active at a time")
            safe_resume_name = safe_filename(resume_name, "resume.txt")
            safe_job_name = safe_filename(job_description_name, "job-description.txt")
            session = Session(
                meeting_url=str(request.meeting_url),
                duration_minutes=request.duration_minutes,
                resume_name=safe_resume_name,
                job_description_name=safe_job_name,
            )
            try:
                paths = await self.artifacts.prepare_inputs(
                    str(session.id),
                    resume_name=safe_resume_name,
                    resume=resume,
                    job_description_name=safe_job_name,
                    job_description=job_description,
                )
                await asyncio.gather(*(extract_document(path) for path in paths))
                await self.repository.create(session)
            except Exception:
                await self.artifacts.delete_all(str(session.id))
                raise
            task = asyncio.create_task(self.runner.run(str(session.id)))
            self._tasks[str(session.id)] = task
            task.add_done_callback(lambda _: self._tasks.pop(str(session.id), None))
            return SessionView.from_session(session)

    async def get(self, session_id: str) -> SessionView:
        session = await self.repository.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return SessionView.from_session(session)

    async def stop(self, session_id: str) -> SessionView:
        session = await self.repository.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        if session.state in {SessionState.COMPLETED, SessionState.STOPPED, SessionState.FAILED}:
            return SessionView.from_session(session)
        await self.runner.stop(session_id)
        task = self._tasks.get(session_id)
        if task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5)
            except TimeoutError:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        return await self.get(session_id)

    async def delete(self, session_id: str) -> None:
        session = await self.repository.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        if session.state not in {SessionState.COMPLETED, SessionState.STOPPED, SessionState.FAILED}:
            raise ActiveSessionError("Stop the active interview before deleting it")
        await self.artifacts.delete_all(session_id)
        await self.repository.delete(session_id)

    async def list_artifacts(self, session_id: str) -> Sequence[Path]:
        await self.get(session_id)
        return await self.artifacts.list(session_id)

    def _validate_upload(self, name: str, content: bytes, label: str) -> None:
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise DocumentError(f"{label} must be PDF, DOCX, or TXT")
        if not content:
            raise DocumentError(f"{label} is empty")
        if len(content) > self.maximum_upload_bytes:
            raise DocumentError(f"{label} exceeds the upload limit")
