import json
from pathlib import Path

from voice_interviewer.artifacts import FilesystemArtifactStore, safe_filename
from voice_interviewer.domain import InterviewNotes, Session, Speaker, Utterance


async def test_artifact_lifecycle(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    session = Session(
        meeting_url="https://meet.google.com/abc-defg-hij",
        duration_minutes=15,
        resume_name="resume.txt",
        job_description_name="job.txt",
    )
    resume_path, job_path = await store.prepare_inputs(
        str(session.id),
        resume_name="../../resume.txt",
        resume=b"Python developer",
        job_description_name="job.txt",
        job_description=b"Backend role",
    )
    assert resume_path.parent == job_path.parent
    assert resume_path.read_bytes() == b"Python developer"

    transcript = [Utterance(Speaker.CANDIDATE, "I built APIs", 100, 900)]
    notes = InterviewNotes(
        summary="Discussed backend work.",
        strengths_observed=["API experience"],
        areas_to_probe=[],
        evidence=["Candidate said they built APIs"],
    )
    await store.write_outputs(session, transcript, notes)
    names = {path.name for path in await store.list(str(session.id))}
    assert names == {"notes.md", "session.json", "transcript.json", "transcript.md"}
    payload = json.loads((store.session_dir(str(session.id)) / "transcript.json").read_text())
    assert payload[0]["speaker"] == "candidate"
    assert "hiring" not in (store.session_dir(str(session.id)) / "notes.md").read_text()

    await store.delete_all(str(session.id))
    assert not store.session_dir(str(session.id)).exists()


def test_safe_filename_removes_path_and_unsafe_characters() -> None:
    assert safe_filename("../../My Resume (final).txt", "fallback.txt") == "My_Resume_final_.txt"
    assert safe_filename("...", "fallback.txt") == "fallback.txt"
