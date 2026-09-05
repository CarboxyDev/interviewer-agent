from __future__ import annotations

import hashlib
import json
import struct
import wave
from pathlib import Path

import pytest

from voice_interviewer.conversation import (
    classify_consent,
    is_consent_withdrawal,
    is_interview_end_request,
    is_repeat_request,
)
from voice_interviewer.documents import extract_document
from voice_interviewer.domain import ConsentDecision, Speaker, Utterance

FIXTURES = Path(__file__).resolve().parents[1] / "benchmarks" / "fixtures" / "v1"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())


def test_fixture_manifest_pins_all_public_inputs() -> None:
    assert MANIFEST["schema_version"] == 1
    assert MANIFEST["dataset_id"] == "candidate-practice-v1"
    assert MANIFEST["synthetic"] is True
    paths = [asset["path"] for asset in MANIFEST["assets"]]
    assert len(paths) == len(set(paths))
    assert set(paths) == {
        str(path.relative_to(FIXTURES))
        for path in FIXTURES.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "README.md"}
    }
    for asset in MANIFEST["assets"]:
        path = (FIXTURES / asset["path"]).resolve()
        assert path.is_relative_to(FIXTURES)
        content = path.read_bytes()
        assert len(content) == asset["size_bytes"]
        assert hashlib.sha256(content).hexdigest() == asset["sha256"]


@pytest.mark.parametrize("name", ["resume.txt", "role.txt"])
async def test_synthetic_documents_work_with_v1_extraction(name: str) -> None:
    text = await extract_document(FIXTURES / name)
    assert text.startswith("SYNTHETIC SAMPLE")
    assert "idempotency" in text
    assert len(text) > 300


def test_reference_utterances_match_nonempty_audio_clips() -> None:
    transcript = json.loads((FIXTURES / "transcript.json").read_text())
    assert transcript["synthetic"] is True
    assert transcript["dataset_id"] == MANIFEST["dataset_id"]
    assert {entry["id"] for entry in transcript["utterances"]} == {
        "consent",
        "answer",
        "repeat",
        "withdrawal",
        "end",
    }
    assert len(transcript["utterances"]) == 5
    audio_assets = {
        asset["path"]: asset for asset in MANIFEST["assets"] if asset["kind"] == "speech"
    }
    assert set(audio_assets) == {entry["audio_path"] for entry in transcript["utterances"]}
    for entry in transcript["utterances"]:
        utterance = Utterance(
            speaker=Speaker(entry["speaker"]),
            text=entry["text"],
            started_at_ms=entry["started_at_ms"],
            ended_at_ms=entry["ended_at_ms"],
        )
        assert utterance.text.strip()
        assert utterance.started_at_ms == 0
        assert utterance.ended_at_ms > 1000
        asset = audio_assets[entry["audio_path"]]
        assert utterance.ended_at_ms == round(asset["frames"] * 1000 / asset["sample_rate_hz"])


@pytest.mark.parametrize(
    "asset",
    [asset for asset in MANIFEST["assets"] if asset["path"].endswith(".wav")],
    ids=lambda asset: asset["path"],
)
def test_fixture_audio_has_expected_format_and_signal(asset: dict[str, object]) -> None:
    with wave.open(str(FIXTURES / str(asset["path"])), "rb") as audio:
        assert audio.getnchannels() == asset["channels"] == 1
        assert audio.getsampwidth() == asset["sample_width_bytes"] == 2
        assert audio.getframerate() == asset["sample_rate_hz"] == 24000
        assert audio.getcomptype() == "NONE"
        assert audio.getnframes() == asset["frames"]
        assert audio.getnframes() >= 24000
        frames = audio.readframes(audio.getnframes())
        assert len(frames) == audio.getnframes() * 2
    samples = [value[0] for value in struct.iter_unpack("<h", frames)]
    if asset["kind"] == "silence":
        assert len(samples) == 24000
        assert not any(samples)
    else:
        # Catch empty/silent synthesis and grossly clipped fixtures, without an STT provider.
        assert sum(sample != 0 for sample in samples) > 2400
        assert max(abs(sample) for sample in samples) > 100
        assert sum(abs(sample) >= 32767 for sample in samples) / len(samples) < 0.01


def test_fixture_control_utterances_record_v1_intent_baseline() -> None:
    transcript = json.loads((FIXTURES / "transcript.json").read_text())
    texts = {entry["id"]: entry["text"] for entry in transcript["utterances"]}
    assert classify_consent(texts["consent"]) is ConsentDecision.GRANTED
    # V1 misses this polite repeat wording. Preserve the probe instead of tuning it to pass.
    assert not is_repeat_request(texts["repeat"])
    assert is_consent_withdrawal(texts["withdrawal"])
    assert is_interview_end_request(texts["end"])
    assert not is_consent_withdrawal(texts["end"])
    assert not is_interview_end_request(texts["answer"])
