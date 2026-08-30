from __future__ import annotations

import math
import time
from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

METRIC_DEFINITIONS = {
    "stt.audio_segment": (
        "Server VAD audio segment from audio_start_ms to audio_end_ms. This includes configured "
        "prefix padding and ending silence."
    ),
    "stt.post_speech": (
        "Time from receipt of the server speech-stopped event to receipt of the final transcript."
    ),
    "llm.request": "Client-observed round-trip time for one LLM operation.",
    "tts.first_audio": "Time from starting TTS synthesis to receiving the first PCM audio chunk.",
    "tts.playback": "Time spent synthesizing and routing one interviewer utterance.",
    "pipeline.response_to_first_audio": (
        "Time from receiving the candidate's final transcript to the first bot audio chunk."
    ),
    "pipeline.response_to_playback_end": (
        "Time from receiving the candidate's final transcript to completed bot playback."
    ),
}


class LatencyTracker:
    def __init__(
        self,
        *,
        models: Mapping[str, str] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._started_at = clock()
        self._models = dict(models or {})
        self._events: list[dict[str, Any]] = []

    def record(
        self,
        stage: str,
        duration_seconds: float,
        *,
        phase: str,
        operation: str | None = None,
        status: str = "completed",
        item_id: str | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "sequence": len(self._events) + 1,
            "stage": stage,
            "phase": phase,
            "status": status,
            "duration_ms": _milliseconds(duration_seconds),
            "session_elapsed_ms": _milliseconds(self._clock() - self._started_at),
        }
        if operation is not None:
            event["operation"] = operation
        if item_id is not None:
            event["item_id"] = item_id
        self._events.append(event)

    def report(self) -> dict[str, object]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for event in self._events:
            if event["status"] != "completed":
                continue
            key = str(event["stage"])
            operation = event.get("operation")
            if operation:
                key = f"{key}.{operation}"
            grouped[key].append(float(event["duration_ms"]))

        summary = {key: _summary(values) for key, values in sorted(grouped.items())}
        return {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "units": "milliseconds",
            "session_duration_ms": _milliseconds(self._clock() - self._started_at),
            "models": self._models,
            "definitions": METRIC_DEFINITIONS,
            "summary": summary,
            "events": list(self._events),
        }


def _milliseconds(seconds: float) -> float:
    return round(max(0.0, seconds) * 1000, 3)


def _summary(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "average_ms": round(sum(ordered) / len(ordered), 3),
        "p50_ms": _percentile(ordered, 0.50),
        "p95_ms": _percentile(ordered, 0.95),
        "max_ms": ordered[-1],
    }


def _percentile(ordered: list[float], percentile: float) -> float:
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]
