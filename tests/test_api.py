from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from tests.fakes import HoldingRunner
from voice_interviewer.api import create_app
from voice_interviewer.artifacts import FilesystemArtifactStore
from voice_interviewer.config import Settings
from voice_interviewer.persistence import SqlAlchemySessionRepository
from voice_interviewer.runtime import Runtime
from voice_interviewer.service import InterviewService


def make_runtime(tmp_path: Path) -> Runtime:
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "data",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}",
        maximum_upload_bytes=1024,
    )
    repository = SqlAlchemySessionRepository(settings.database_url)
    artifacts = FilesystemArtifactStore(settings.artifacts_dir)
    runner = HoldingRunner(repository)
    service = InterviewService(
        repository=repository,
        artifacts=artifacts,
        runner=runner,
        maximum_upload_bytes=settings.maximum_upload_bytes,
    )
    return Runtime(settings, repository, artifacts, service, None)


def create_interview(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/v1/interviews",
        data={
            "meeting_url": "https://meet.google.com/abc-defg-hij",
            "meeting_authorization_confirmed": "true",
            "duration_minutes": "15",
        },
        files={
            "resume": ("resume.txt", b"Python backend engineer", "text/plain"),
            "job_description": ("job.txt", b"Build backend APIs", "text/plain"),
        },
    )
    assert response.status_code == 202, response.text
    return cast(dict[str, object], response.json())


def test_api_session_lifecycle_and_conflicts(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with TestClient(create_app(runtime)) as client:
        assert client.get("/health/live").json()["status"] == "ok"
        assert client.get("/health/ready").json()["status"] == "not_ready"

        missing_job = client.post(
            "/v1/interviews",
            data={
                "meeting_url": "https://meet.google.com/abc-defg-hij",
                "meeting_authorization_confirmed": "true",
            },
            files={"resume": ("resume.txt", b"resume", "text/plain")},
        )
        assert missing_job.status_code == 422

        invalid_url = client.post(
            "/v1/interviews",
            data={
                "meeting_url": "https://example.com/not-meet",
                "meeting_authorization_confirmed": "true",
                "job_description_text": "Backend role",
            },
            files={"resume": ("resume.txt", b"resume", "text/plain")},
        )
        assert invalid_url.status_code == 422

        created = create_interview(client)
        session_id = str(created["id"])
        recent = client.get("/v1/interviews", params={"limit": 1, "offset": 0})
        assert recent.status_code == 200
        assert recent.json() == {
            "items": [created],
            "total": 1,
            "limit": 1,
            "offset": 0,
        }
        assert client.get("/v1/interviews", params={"limit": 0}).status_code == 422
        assert client.get(f"/v1/interviews/{session_id}").status_code == 200
        assert client.get(f"/v1/interviews/{session_id}/artifacts").json() == []
        assert client.get(f"/v1/interviews/{session_id}/artifacts.zip").status_code == 409

        second = client.post(
            "/v1/interviews",
            data={
                "meeting_url": "https://meet.google.com/xyz-abcd-efg",
                "meeting_authorization_confirmed": "true",
                "job_description_text": "Another role",
            },
            files={"resume": ("resume.txt", b"resume", "text/plain")},
        )
        assert second.status_code == 409
        assert client.delete(f"/v1/interviews/{session_id}").status_code == 409

        stopped = client.post(f"/v1/interviews/{session_id}/stop")
        assert stopped.status_code == 200
        assert stopped.json()["state"] == "STOPPED"
        assert client.delete(f"/v1/interviews/{session_id}").status_code == 204
        assert client.get(f"/v1/interviews/{session_id}").status_code == 404
        assert client.post(f"/v1/interviews/{session_id}/stop").status_code == 404


def test_api_downloads_artifact_archive(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with TestClient(create_app(runtime)) as client:
        created = create_interview(client)
        session_id = str(created["id"])
        assert client.post(f"/v1/interviews/{session_id}/stop").status_code == 200
        directory = runtime.artifacts.session_dir(session_id)
        (directory / "transcript.md").write_text("# Transcript", encoding="utf-8")

        listing = client.get(f"/v1/interviews/{session_id}/artifacts")
        assert listing.json()[0]["name"] == "transcript.md"
        direct_download = client.get(f"/v1/interviews/{session_id}/artifacts/transcript.md")
        assert direct_download.status_code == 200
        assert direct_download.content == b"# Transcript"
        assert "attachment" in direct_download.headers["content-disposition"]
        assert client.get(f"/v1/interviews/{session_id}/artifacts/resume.txt").status_code == 404
        download = client.get(f"/v1/interviews/{session_id}/artifacts.zip")
        assert download.status_code == 200
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            assert archive.namelist() == ["transcript.md"]


def test_api_defaults_to_30_minutes(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with TestClient(create_app(runtime)) as client:
        response = client.post(
            "/v1/interviews",
            data={
                "meeting_url": "https://meet.google.com/abc-defg-hij",
                "meeting_authorization_confirmed": "true",
                "job_description_text": "Backend role",
            },
            files={"resume": ("resume.txt", b"Python backend engineer", "text/plain")},
        )

        assert response.status_code == 202
        assert response.json()["duration_minutes"] == 30
