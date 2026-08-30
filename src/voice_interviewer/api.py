from __future__ import annotations

import asyncio
import json
import os
import tempfile
import zipfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, cast

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.background import BackgroundTask

from voice_interviewer.doctor import is_ready, run_checks
from voice_interviewer.domain import (
    ArtifactView,
    HealthView,
    SessionCreate,
    SessionPage,
    SessionView,
)
from voice_interviewer.errors import ActiveSessionError, DocumentError, SessionNotFoundError
from voice_interviewer.runtime import Runtime, build_runtime


def create_app(runtime: Runtime | None = None) -> FastAPI:
    application_runtime = runtime or build_runtime()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await application_runtime.initialize()
        try:
            yield
        finally:
            await application_runtime.close()

    app = FastAPI(
        title="Interviewer Voice Agent",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.runtime = application_runtime

    @app.get("/health/live", response_model=HealthView)
    async def live() -> HealthView:
        return HealthView(status="ok", checks={"process": True})

    @app.get("/health/ready", response_model=HealthView)
    async def ready() -> HealthView:
        checks = await run_checks(application_runtime.settings)
        return HealthView(status="ok" if is_ready(checks) else "not_ready", checks=checks)

    @app.post(
        "/v1/interviews",
        response_model=SessionView,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_interview(
        meeting_url: Annotated[str, Form()],
        meeting_authorization_confirmed: Annotated[bool, Form()],
        resume: Annotated[UploadFile, File()],
        duration_minutes: Annotated[int, Form()] = 30,
        job_description: Annotated[UploadFile | None, File()] = None,
        job_description_text: Annotated[str | None, Form()] = None,
    ) -> SessionView:
        if (job_description is None) == (job_description_text is None):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Provide exactly one of job_description or job_description_text",
            )
        try:
            request = SessionCreate.model_validate(
                {
                    "meeting_url": meeting_url,
                    "duration_minutes": duration_minutes,
                    "meeting_authorization_confirmed": meeting_authorization_confirmed,
                }
            )
            resume_bytes = await _read_upload(
                resume,
                application_runtime.settings.maximum_upload_bytes,
            )
            if job_description is not None:
                job_name = job_description.filename or "job-description.txt"
                job_bytes = await _read_upload(
                    job_description,
                    application_runtime.settings.maximum_upload_bytes,
                )
            else:
                job_name = "job-description.txt"
                job_bytes = (job_description_text or "").encode("utf-8")
            return await application_runtime.service.create(
                request,
                resume_name=resume.filename or "resume.txt",
                resume=resume_bytes,
                job_description_name=job_name,
                job_description=job_bytes,
            )
        except ValidationError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                exc.errors(include_context=False),
            ) from exc
        except DocumentError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        except ActiveSessionError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    @app.get("/v1/interviews", response_model=SessionPage)
    async def list_interviews(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> SessionPage:
        return await application_runtime.service.list_recent(limit=limit, offset=offset)

    @app.get("/v1/interviews/{session_id}", response_model=SessionView)
    async def get_interview(session_id: str) -> SessionView:
        return await _get_or_404(application_runtime, session_id)

    @app.post("/v1/interviews/{session_id}/stop", response_model=SessionView)
    async def stop_interview(session_id: str) -> SessionView:
        try:
            return await application_runtime.service.stop(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found") from exc

    @app.get("/v1/interviews/{session_id}/artifacts", response_model=list[ArtifactView])
    async def list_artifacts(session_id: str) -> list[ArtifactView]:
        try:
            paths = await application_runtime.artifacts.list(session_id)
            await application_runtime.service.get(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found") from exc
        return [ArtifactView(name=path.name, size_bytes=path.stat().st_size) for path in paths]

    @app.get("/v1/interviews/{session_id}/artifacts.zip")
    async def download_artifacts(session_id: str) -> FileResponse:
        try:
            paths = await application_runtime.artifacts.list(session_id)
            await application_runtime.service.get(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found") from exc
        if not paths:
            raise HTTPException(status.HTTP_409_CONFLICT, "Artifacts are not ready")
        archive = await asyncio.to_thread(_zip_artifacts, session_id, paths)
        return FileResponse(
            archive,
            filename=f"interview-{session_id}.zip",
            media_type="application/zip",
            background=BackgroundTask(os.unlink, archive),
        )

    @app.get("/v1/interviews/{session_id}/metrics")
    async def get_metrics(session_id: str) -> dict[str, object]:
        try:
            paths = await application_runtime.artifacts.list(session_id)
            await application_runtime.service.get(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found") from exc
        metrics_path = next((path for path in paths if path.name == "metrics.json"), None)
        if metrics_path is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Metrics are not ready")
        content = await asyncio.to_thread(metrics_path.read_text, encoding="utf-8")
        return cast(dict[str, object], json.loads(content))

    @app.get("/v1/interviews/{session_id}/artifacts/{artifact_name}")
    async def download_artifact(session_id: str, artifact_name: str) -> FileResponse:
        try:
            paths = await application_runtime.artifacts.list(session_id)
            await application_runtime.service.get(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found") from exc
        artifact = next((path for path in paths if path.name == artifact_name), None)
        if artifact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact not found or not ready")
        return FileResponse(artifact, filename=artifact.name)

    @app.delete("/v1/interviews/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_interview(session_id: str) -> None:
        try:
            await application_runtime.service.delete(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found") from exc
        except ActiveSessionError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    return app


async def _read_upload(upload: UploadFile, maximum_bytes: int) -> bytes:
    content = await upload.read(maximum_bytes + 1)
    if len(content) > maximum_bytes:
        raise DocumentError(f"{upload.filename or 'upload'} exceeds the upload limit")
    return content


async def _get_or_404(runtime: Runtime, session_id: str) -> SessionView:
    try:
        return await runtime.service.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found") from exc


def _zip_artifacts(session_id: str, paths: list[Path]) -> str:
    descriptor, archive_path = tempfile.mkstemp(prefix=f"interview-{session_id}-", suffix=".zip")
    os.close(descriptor)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, arcname=path.name)
    return archive_path


app = create_app()
