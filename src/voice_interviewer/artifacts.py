from __future__ import annotations

import asyncio
import json
import re
import shutil
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from voice_interviewer.domain import InterviewNotes, Session, Utterance

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
OUTPUT_NAMES = {
    "interview.mp3",
    "transcript.json",
    "transcript.md",
    "notes.md",
    "session.json",
}


def safe_filename(name: str, fallback: str) -> str:
    clean = SAFE_NAME.sub("_", Path(name).name).strip("._")
    return clean[:120] or fallback


class FilesystemArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    async def prepare_inputs(
        self,
        session_id: str,
        *,
        resume_name: str,
        resume: bytes,
        job_description_name: str,
        job_description: bytes,
    ) -> tuple[Path, Path]:
        directory = self.session_dir(session_id) / "input"
        resume_path = directory / safe_filename(resume_name, "resume.txt")
        job_path = directory / safe_filename(job_description_name, "job-description.txt")

        def write() -> None:
            directory.mkdir(parents=True, exist_ok=False)
            resume_path.write_bytes(resume)
            job_path.write_bytes(job_description)

        await asyncio.to_thread(write)
        return resume_path, job_path

    async def list(self, session_id: str) -> list[Path]:
        directory = self.session_dir(session_id)
        if not directory.is_dir():
            return []
        return sorted(
            path
            for path in await asyncio.to_thread(lambda: list(directory.iterdir()))
            if path.is_file() and path.name in OUTPUT_NAMES
        )

    async def write_outputs(
        self,
        session: Session,
        transcript: Sequence[Utterance],
        notes: InterviewNotes,
    ) -> None:
        directory = self.session_dir(str(session.id))
        transcript_data = [
            {
                "speaker": item.speaker.value,
                "text": item.text,
                "started_at_ms": item.started_at_ms,
                "ended_at_ms": item.ended_at_ms,
            }
            for item in transcript
        ]
        transcript_markdown = "# Interview transcript\n\n" + "\n\n".join(
            f"**{item.speaker.value.title()} [{item.started_at_ms / 1000:.1f}s]**\n\n{item.text}"
            for item in transcript
        )
        notes_markdown = (
            "# Interview notes\n\n"
            f"## Summary\n\n{notes.summary}\n\n"
            "## Strengths observed\n\n"
            + _bullets(notes.strengths_observed)
            + "\n\n## Areas to probe\n\n"
            + _bullets(notes.areas_to_probe)
            + "\n\n## Evidence\n\n"
            + _bullets(notes.evidence)
            + "\n"
        )
        session_data = asdict(session)

        def write() -> None:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "transcript.json").write_text(
                json.dumps(transcript_data, indent=2),
                encoding="utf-8",
            )
            (directory / "transcript.md").write_text(transcript_markdown, encoding="utf-8")
            (directory / "notes.md").write_text(notes_markdown, encoding="utf-8")
            (directory / "session.json").write_text(
                json.dumps(session_data, indent=2, default=str),
                encoding="utf-8",
            )

        await asyncio.to_thread(write)

    async def delete_content(self, session_id: str) -> None:
        directory = self.session_dir(session_id)
        await asyncio.to_thread(shutil.rmtree, directory, True)

    async def delete_all(self, session_id: str) -> None:
        await self.delete_content(session_id)


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None observed"
