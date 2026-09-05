"""V2-004 deterministic aggregation with no provider or real-session inputs."""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_latency", ROOT / "benchmarks/analyze_latency.py"
)
assert SPEC is not None and SPEC.loader is not None
latency = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(latency)
TEMPLATE = json.loads((ROOT / "benchmarks/run-template.json").read_text())


def campaign() -> dict[str, Any]:
    run = json.loads(json.dumps(TEMPLATE))
    run["status"] = "partial"
    run["attempts"] = [
        {
            "attempt_id": f"attempt-{i + 1:02d}",
            "round": i // 4 + 1,
            "probe_id": TEMPLATE["probe_order"][i % 4],
            "status": "not_run",
            "terminal_state": None,
        }
        for i in range(20)
    ]
    return run  # type: ignore[no-any-return]


def collected(run: dict[str, Any], index: int, status: str = "completed") -> str:
    attempt = run["attempts"][index]
    attempt.update(status=status, terminal_state="COMPLETED" if status == "completed" else "FAILED")
    return str(attempt["attempt_id"])


def event(
    stage: str,
    duration: float,
    phase: str = "interview",
    status: str = "completed",
    operation: str | None = None,
) -> dict[str, Any]:
    result = {"stage": stage, "phase": phase, "status": status, "duration_ms": duration}
    if operation:
        result["operation"] = operation
    return result


def metric_report(events: list[dict[str, Any]], ordinal: int = 1) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "units": "milliseconds",
        "generated_at": f"2026-09-05T00:00:{ordinal:02d}+00:00",
        "models": {key: TEMPLATE["configuration"][f"{key}_model"] for key in ("stt", "llm", "tts")},
        "events": [dict(value, sequence=index + 1) for index, value in enumerate(events)],
        # The analyzer must ignore pre-aggregated summaries, including deliberately wrong values.
        "summary": {"pipeline.response_to_first_audio": {"p50_ms": 999999}},
    }


def turn(
    duration: float, phase: str = "interview", status: str = "completed"
) -> list[dict[str, Any]]:
    return [
        event("tts.first_audio", 100, phase),
        event("pipeline.response_to_first_audio", duration, phase),
        event("tts.playback", duration + 1000, phase, status),
    ]


def primary(result: dict[str, Any]) -> dict[str, Any]:
    return next(
        row
        for row in result["latency"]
        if row["stage"] == "pipeline.response_to_first_audio" and row["phase"] == "interview"
    )


def test_empty_campaign_keeps_unknown_latency_cost_and_all_attempts() -> None:
    result = latency.aggregate(campaign(), {}, TEMPLATE)
    row = primary(result)
    assert row["count"] == 0
    assert row["p50_ms"] is None
    assert row["p95_ms"] is None
    assert row["missing_count"] is None
    assert result["attempt_accounting"]["not_run"] == 20
    assert result["provider_cost"] is None
    assert result["candidate_perceived_response"] is None
    assert result["interruption_stop"] is None
    assert result["provenance_verified"] is False


def test_pools_raw_samples_and_keeps_phases_and_operations_separate() -> None:
    run = campaign()
    first, second = collected(run, 0), collected(run, 1)
    reports = {
        first: metric_report(
            turn(100)
            + turn(200)
            + turn(300, "opening")
            + [event("llm.request", 40, "preparation", operation="prepare")]
        ),
        second: metric_report([*turn(900), event("llm.request", 60, operation="next_turn")], 2),
    }
    result = latency.aggregate(run, reports, TEMPLATE)
    row = primary(result)
    assert (row["count"], row["p50_ms"], row["p95_ms"]) == (3, 200, 900)
    assert row["small_sample"] is True
    assert row["excluded_count"] == 0
    opening = next(
        r for r in result["latency"] if r["stage"] == row["stage"] and r["phase"] == "opening"
    )
    assert opening["p50_ms"] == 300
    assert {r["operation"] for r in result["latency"] if r["stage"] == "llm.request"} == {
        "prepare",
        "next_turn",
    }


def test_nearest_rank_quantiles_at_twenty_samples() -> None:
    run = campaign()
    attempt = collected(run, 0)
    report = metric_report([e for value in range(1, 21) for e in turn(value)])
    row = primary(latency.aggregate(run, {attempt: report}, TEMPLATE))
    assert (row["count"], row["p50_ms"], row["p95_ms"], row["max_ms"]) == (20, 10, 19, 20)
    assert row["small_sample"] is False


@pytest.mark.parametrize("status", ["failed", "interrupted"])
def test_partial_playback_excludes_all_onsets_in_affected_phase(status: str) -> None:
    run = campaign()
    attempt = collected(run, 0)
    report = metric_report(turn(100) + turn(200, status=status) + turn(300, "opening"))
    result = latency.aggregate(run, {attempt: report}, TEMPLATE)
    row = primary(result)
    assert row["count"] == 0
    assert row["exclusions"] == {"unpaired_or_partial_playback": 2}
    playback = next(
        r for r in result["latency"] if r["stage"] == "tts.playback" and r["phase"] == "interview"
    )
    assert playback[f"{status}_events"] == 1
    assert playback["excluded_count"] == 1
    assert any(r["phase"] == "opening" and r["count"] == 1 for r in result["latency"])


def test_orphan_first_audio_without_playback_is_excluded() -> None:
    run = campaign()
    attempt = collected(run, 0)
    report = metric_report(turn(100)[:-1])
    row = primary(latency.aggregate(run, {attempt: report}, TEMPLATE))
    assert row["count"] == 0
    assert row["p50_ms"] is None


@pytest.mark.parametrize("status", ["failed", "incomplete"])
def test_failed_attempt_is_counted_without_polluting_latency(status: str) -> None:
    run = campaign()
    attempt = collected(run, 0, status)
    result = latency.aggregate(run, {attempt: metric_report(turn(100))}, TEMPLATE)
    assert primary(result)["exclusions"] == {"ineligible_attempt": 1}
    assert result["attempt_accounting"][status] == 1
    assert result["attempt_accounting"]["scheduled"] == 20
    assert result["attempt_accounting"]["not_run"] == 19


def test_missing_artifact_is_counted_separately_from_missing_stage_events() -> None:
    run = campaign()
    collected(run, 0)
    collected(run, 2, "failed")
    result = latency.aggregate(run, {}, TEMPLATE)
    assert result["attempt_accounting"]["missing_metric_files"] == 2
    assert primary(result)["missing_count"] is None


def test_withdrawal_artifact_is_rejected_and_absence_is_expected() -> None:
    run = campaign()
    attempt = collected(run, 3)
    run["attempts"][3]["terminal_state"] = "STOPPED"
    result = latency.aggregate(run, {}, TEMPLATE)
    assert result["attempt_accounting"]["withdrawal_attempts_excluded"] == 1
    assert result["attempt_accounting"]["missing_metric_files"] == 0
    with pytest.raises(latency.AnalysisError, match="Withdrawal"):
        latency.aggregate(run, {attempt: metric_report(turn(100))}, TEMPLATE)


@pytest.mark.parametrize(
    "field", ["dataset_manifest_sha256", "configuration", "runtime_baseline_commit"]
)
def test_configuration_and_dataset_mixing_are_rejected(field: str) -> None:
    run = campaign()
    run[field] = "different"
    with pytest.raises(latency.AnalysisError, match="fixed protocol"):
        latency.aggregate(run, {}, TEMPLATE)


def test_missing_duplicate_or_reordered_scheduled_attempts_are_rejected() -> None:
    for change in ("missing", "duplicate", "reordered"):
        run = campaign()
        if change == "missing":
            run["attempts"].pop()
        elif change == "duplicate":
            run["attempts"][1] = run["attempts"][0]
        else:
            run["attempts"].reverse()
        with pytest.raises(latency.AnalysisError):
            latency.aggregate(run, {}, TEMPLATE)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "100", 10**400])
def test_invalid_durations_cannot_become_measurements(value: object) -> None:
    run = campaign()
    attempt = collected(run, 0)
    report = metric_report(turn(100))
    report["events"][0]["duration_ms"] = value
    with pytest.raises(latency.AnalysisError, match="finite nonnegative"):
        latency.aggregate(run, {attempt: report}, TEMPLATE)


@pytest.mark.parametrize(
    "field,value",
    [
        ("stage", "secret-stage"),
        ("phase", "secret-phase"),
        ("status", "unknown"),
        ("sequence", 5),
        ("operation", "unknown"),
    ],
)
def test_invalid_events_fail_without_exposing_input_values(field: str, value: object) -> None:
    run = campaign()
    attempt = collected(run, 0)
    report = metric_report(turn(100))
    report["events"][0][field] = value
    with pytest.raises(latency.AnalysisError) as error:
        latency.aggregate(run, {attempt: report}, TEMPLATE)
    assert str(value) not in str(error.value)


def test_model_mismatch_is_rejected() -> None:
    run = campaign()
    attempt = collected(run, 0)
    report = metric_report(turn(100))
    report["models"]["llm"] = "different-model"
    with pytest.raises(latency.AnalysisError, match="models differ"):
        latency.aggregate(run, {attempt: report}, TEMPLATE)


def test_duplicate_artifact_cannot_double_count_samples() -> None:
    run = campaign()
    first, second = collected(run, 0), collected(run, 1)
    report = metric_report(turn(100))
    with pytest.raises(latency.AnalysisError, match="Duplicate metric artifact"):
        latency.aggregate(run, {first: report, second: report}, TEMPLATE)


def test_unknown_and_unrun_attempts_cannot_supply_metrics() -> None:
    for attempt in ("attempt-01", "attempt-99"):
        with pytest.raises(latency.AnalysisError):
            latency.aggregate(campaign(), {attempt: metric_report(turn(100))}, TEMPLATE)


def test_output_is_allowlisted_and_does_not_echo_free_text_or_identifiers() -> None:
    run = campaign()
    attempt = collected(run, 0)
    run["campaign_id"] = "private-canary"
    run["limitations"].append("private-canary")
    run["attempts"][0]["review"] = [{"evidence": "private-canary"}]
    report = metric_report(turn(100))
    report["events"][0]["item_id"] = "private-canary"
    report["session_url"] = "private-canary"
    result = latency.aggregate(run, {attempt: report}, TEMPLATE)
    assert "private-canary" not in json.dumps(result)


def test_more_response_onsets_than_audio_chunks_are_excluded() -> None:
    run = campaign()
    attempt = collected(run, 0)
    report = metric_report([*turn(100), event("pipeline.response_to_first_audio", 200)])
    row = primary(latency.aggregate(run, {attempt: report}, TEMPLATE))
    assert row["count"] == 0
    assert row["excluded_count"] == 2


def test_cli_reads_unscored_campaign_without_writing_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_path = tmp_path / "run.json"
    content = json.dumps(campaign())
    run_path.write_text(content)
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    monkeypatch.setattr(
        latency.sys, "argv", ["analyze", str(run_path), "--metrics-dir", str(metrics)]
    )
    assert latency.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["attempt_accounting"]["not_run"] == 20
    assert primary(output)["p50_ms"] is None
    assert run_path.read_text() == content
    assert list(metrics.iterdir()) == []


def test_cli_refuses_session_exports_in_metrics_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps(campaign()))
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "session.json").write_text('{"private": "synthetic-private-canary"}')
    monkeypatch.setattr(
        latency.sys, "argv", ["analyze", str(run_path), "--metrics-dir", str(metrics)]
    )
    assert latency.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "synthetic-private-canary" not in output.err
    assert "only scheduled" in output.err


def test_accepts_actual_v1_latency_tracker_report() -> None:
    from voice_interviewer.metrics import LatencyTracker

    run = campaign()
    attempt = collected(run, 0)
    tracker = LatencyTracker(
        models={key: TEMPLATE["configuration"][f"{key}_model"] for key in ("stt", "llm", "tts")},
        clock=lambda: 10.0,
    )
    tracker.record("tts.first_audio", 0.1, phase="interview")
    tracker.record("pipeline.response_to_first_audio", 3.0, phase="interview")
    tracker.record("tts.playback", 8.0, phase="interview")
    result = latency.aggregate(run, {attempt: tracker.report()}, TEMPLATE)
    assert primary(result)["p50_ms"] == 3000
    assert primary(result)["count"] == 1
