"""V2-004: summarize raw V1 latency events without inventing missing measurements."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    "stt.audio_segment",
    "stt.post_speech",
    "llm.request",
    "tts.first_audio",
    "tts.playback",
    "pipeline.response_to_first_audio",
    "pipeline.response_to_playback_end",
}
PHASES = {
    "preparation",
    "consent",
    "opening",
    "interview",
    "repeat",
    "clarification",
    "closing",
    "finalization",
}
STATUSES = {"completed", "failed", "interrupted"}
ONSET_STAGES = {"tts.first_audio", "pipeline.response_to_first_audio"}
PRIMARY = ("pipeline.response_to_first_audio", "interview", "")
Key = tuple[str, str, str]


class AnalysisError(ValueError):
    """A public-safe error that contains no input values or raw records."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AnalysisError(message)


def validate_campaign(run: dict[str, Any], template: dict[str, Any]) -> list[dict[str, Any]]:
    for key in (
        "schema_version",
        "protocol_id",
        "runtime_baseline_commit",
        "dataset_id",
        "dataset_manifest_sha256",
        "configuration",
        "scheduled_attempts",
        "probe_order",
        "rounds",
    ):
        require(run.get(key) == template[key], "Campaign does not match this fixed protocol.")
    require(run.get("evidence_lane") == "live_meet", "Campaign has an unsupported evidence lane.")
    require(run.get("status") in {"blocked", "partial", "completed"}, "Campaign status is invalid.")
    attempts = cast(list[dict[str, Any]], run.get("attempts"))
    require(
        isinstance(attempts, list) and len(attempts) == 20,
        "All 20 scheduled attempts are required.",
    )
    for index, attempt in enumerate(attempts):
        require(isinstance(attempt, dict), "Attempt record must be an object.")
        require(
            attempt.get("attempt_id") == f"attempt-{index + 1:02d}"
            and attempt.get("round") == index // 4 + 1
            and attempt.get("probe_id") == template["probe_order"][index % 4],
            "Attempt identity/order differs from the fixed probe matrix.",
        )
        require(
            attempt.get("status") in {"completed", "failed", "incomplete", "not_run"},
            "Attempt status is invalid.",
        )
        if attempt["status"] == "not_run":
            require(
                attempt.get("terminal_state") is None,
                "An unrun attempt cannot have a terminal state.",
            )
        if attempt["status"] == "completed":
            require(
                attempt.get("terminal_state") in {"COMPLETED", "STOPPED"},
                "Completed collection needs an expected terminal state.",
            )
    return attempts


def validate_report(report: dict[str, Any], models: dict[str, str]) -> list[dict[str, Any]]:
    require(report.get("schema_version") == 1, "Unsupported raw metric schema.")
    require(report.get("units") == "milliseconds", "Metric units must be milliseconds.")
    require(report.get("models") == models, "Metric models differ from the campaign configuration.")
    events = cast(list[dict[str, Any]], report.get("events"))
    require(isinstance(events, list), "Raw metric events are required; summaries are not input.")
    for index, event in enumerate(events):
        require(isinstance(event, dict), "Metric event must be an object.")
        require(
            type(event.get("sequence")) is int and event["sequence"] == index + 1,
            "Metric sequences must be contiguous and unique.",
        )
        require(
            event.get("stage") in STAGES and event.get("phase") in PHASES,
            "Unknown metric stage or phase.",
        )
        require(event.get("status") in STATUSES, "Unknown metric status.")
        value = cast(float, event.get("duration_ms"))
        require(
            type(value) in {int, float} and 0 <= value <= sys.float_info.max,
            "Metric durations must be finite nonnegative numbers.",
        )
        operation = event.get("operation")
        require(
            operation in {"prepare", "next_turn", "notes"}
            if event["stage"] == "llm.request"
            else operation is None,
            "Unexpected metric operation.",
        )
    return events


def quantiles(values: list[float]) -> dict[str, int | float | None]:
    ordered = sorted(values)
    count = len(ordered)
    return {
        "count": count,
        "p50_ms": ordered[math.ceil(0.5 * count) - 1] if count else None,
        "p95_ms": ordered[math.ceil(0.95 * count) - 1] if count else None,
        "max_ms": ordered[-1] if count else None,
    }


def aggregate(
    run: dict[str, Any],
    reports: dict[str, dict[str, Any]],
    template: dict[str, Any],
) -> dict[str, Any]:
    attempts = validate_campaign(run, template)
    by_id = {attempt["attempt_id"]: attempt for attempt in attempts}
    require(set(reports) <= set(by_id), "Metrics include an unknown or unscheduled attempt.")
    models = {stage: run["configuration"][f"{stage}_model"] for stage in ("stt", "llm", "tts")}
    values: dict[Key, list[float]] = defaultdict(list)
    exclusions: dict[Key, Counter[str]] = defaultdict(Counter)
    statuses: dict[Key, Counter[str]] = defaultdict(Counter)
    # Include the primary comparison even when nothing was collected; null is never zero latency.
    values[PRIMARY] = []
    seen: set[str] = set()
    for attempt_id, report in reports.items():
        attempt = by_id[attempt_id]
        require(attempt["status"] != "not_run", "An unrun attempt cannot have metric artifacts.")
        require(
            attempt["probe_id"] != "withdraw_after_answer",
            "Withdrawal metrics must not be retained or analyzed.",
        )
        events = validate_report(report, models)
        try:
            timestamp = datetime.fromisoformat(report["generated_at"])
            require(timestamp.tzinfo is not None, "Metric timestamp needs a timezone.")
        except (KeyError, ValueError, TypeError) as error:
            raise AnalysisError("Metric generation timestamp is invalid.") from error
        identity = hashlib.sha256(
            json.dumps(
                [timestamp.isoformat(), events],
                sort_keys=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        require(identity not in seen, "Duplicate metric artifact across attempts.")
        seen.add(identity)
        playback = [event for event in events if event["stage"] == "tts.playback"]
        compromised = {event["phase"] for event in playback if event["status"] != "completed"}
        completed = Counter(event["phase"] for event in playback if event["status"] == "completed")
        first_chunks = Counter(
            event["phase"] for event in events if event["stage"] == "tts.first_audio"
        )
        response_onsets = Counter(
            event["phase"]
            for event in events
            if event["stage"] == "pipeline.response_to_first_audio"
        )
        compromised.update(
            phase
            for phase in PHASES
            if first_chunks[phase] != completed[phase]
            or response_onsets[phase] > first_chunks[phase]
        )
        for event in events:
            key = (event["stage"], event["phase"], event.get("operation") or "")
            values.setdefault(key, [])
            statuses[key][event["status"]] += 1
            reason = None
            if attempt["status"] != "completed" or attempt["terminal_state"] != "COMPLETED":
                reason = "ineligible_attempt"
            elif event["status"] != "completed":
                reason = event["status"]
            elif event["stage"] in ONSET_STAGES and (
                event["phase"] in compromised or completed[event["phase"]] == 0
            ):
                # V1 has no uniform turn ID. Exclude all onsets in the affected attempt/phase.
                reason = "unpaired_or_partial_playback"
            if reason:
                exclusions[key][reason] += 1
            else:
                values[key].append(float(event["duration_ms"]))
    rows = [
        {
            "stage": key[0],
            "phase": key[1],
            "operation": key[2] or None,
            **quantiles(samples),
            "small_sample": len(samples) < 20,
            "missing_count": None,
            "missing_reason": "Expected stage/phase event counts are not recorded in V1.",
            "failed_events": statuses[key]["failed"],
            "interrupted_events": statuses[key]["interrupted"],
            "excluded_count": sum(exclusions[key].values()),
            "exclusions": dict(sorted(exclusions[key].items())),
        }
        for key, samples in sorted(values.items())
    ]
    statuses_count = Counter(attempt["status"] for attempt in attempts)
    expected_artifacts = [
        attempt["attempt_id"]
        for attempt in attempts
        if attempt["status"] != "not_run" and attempt["probe_id"] != "withdraw_after_answer"
    ]
    return {
        "schema_version": 1,
        "task_id": "V2-004",
        "protocol_id": template["protocol_id"],
        "scope": "Server latency analysis only. Campaign and release acceptance remain separate.",
        "provenance_verified": False,
        "attempt_accounting": {
            "scheduled": 20,
            **{
                status: statuses_count[status]
                for status in ("completed", "failed", "incomplete", "not_run")
            },
            "metric_files_supplied": len(reports),
            "missing_metric_files": len(set(expected_artifacts) - set(reports)),
            "withdrawal_attempts_excluded": sum(
                attempt["status"] != "not_run" and attempt["probe_id"] == "withdraw_after_answer"
                for attempt in attempts
            ),
        },
        "latency": rows,
        "provider_cost": None,
        "candidate_perceived_response": None,
        "interruption_stop": None,
        "limitations": [
            "Image provenance, human review, consent, and deletion need separate verification.",
            "First audio measures generated server PCM, not candidate-audible response.",
            "Failed/incomplete attempts are excluded from latency and retained in accounting.",
            "Ambiguous onset samples are excluded for the entire affected attempt/phase.",
            "Stage gaps, cost, audible onset, and interruption-stop timing remain unknown.",
        ],
    }


def read_object(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text())
    require(isinstance(result, dict), "Input must be a JSON object.")
    return cast(dict[str, Any], result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="Local unscored or collected campaign run.json")
    parser.add_argument(
        "--metrics-dir", type=Path, required=True, help="Only attempt-NN.json metric exports"
    )
    args = parser.parse_args()
    try:
        template = read_object(ROOT / "benchmarks/run-template.json")
        run = read_object(args.run)
        attempts = validate_campaign(run, template)
        reports = {}
        require(args.metrics_dir.is_dir(), "Metrics directory must exist, even if empty.")
        allowed = {f"{attempt['attempt_id']}.json" for attempt in attempts}
        require(
            all(path.name in allowed for path in args.metrics_dir.iterdir()),
            "Metrics directory must contain only scheduled attempt-NN.json files.",
        )
        for path in args.metrics_dir.iterdir():
            require(not path.is_symlink(), "Metric exports must not be symbolic links.")
            reports[path.stem] = read_object(path)
        print(json.dumps(aggregate(run, reports, template), indent=2, allow_nan=False))  # noqa: T201
        return 0
    except (AnalysisError, OSError, KeyError, TypeError, ValueError) as error:
        message = (
            str(error)
            if isinstance(error, AnalysisError)
            else "Invalid or unavailable local analysis input."
        )
        print(json.dumps({"task_id": "V2-004", "error": message}), file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
