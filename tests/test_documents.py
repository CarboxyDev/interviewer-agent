from pathlib import Path

import pytest

from voice_interviewer.documents import extract_document
from voice_interviewer.errors import DocumentError


async def test_extract_text_document(tmp_path: Path) -> None:
    document = tmp_path / "resume.txt"
    document.write_text("  Python engineer  \n\n Builds APIs ", encoding="utf-8")
    assert await extract_document(document) == "Python engineer\nBuilds APIs"


async def test_empty_or_unsupported_document_fails(tmp_path: Path) -> None:
    empty = tmp_path / "resume.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(DocumentError, match="No extractable text"):
        await extract_document(empty)

    unsupported = tmp_path / "resume.md"
    unsupported.write_text("content", encoding="utf-8")
    with pytest.raises(DocumentError, match="Unsupported"):
        await extract_document(unsupported)
