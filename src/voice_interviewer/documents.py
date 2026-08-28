from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from voice_interviewer.errors import DocumentError

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _extract_sync(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise DocumentError(f"Unsupported document type: {suffix or 'missing extension'}")

    try:
        if suffix == ".txt":
            text = path.read_text(encoding="utf-8-sig")
        elif suffix == ".pdf":
            reader = PdfReader(path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            document = Document(BytesIO(path.read_bytes()))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except (OSError, UnicodeError, ValueError) as exc:
        raise DocumentError(f"Could not read {path.name}: {exc}") from exc

    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        raise DocumentError(f"No extractable text found in {path.name}; OCR is not supported")
    return normalized


async def extract_document(path: Path) -> str:
    return await asyncio.to_thread(_extract_sync, path)
