from voice_interviewer.metrics import LatencyTracker


def test_latency_tracker_reports_stage_and_operation_percentiles() -> None:
    tracker = LatencyTracker(models={"llm": "test-model"}, clock=lambda: 10.0)
    tracker.record("llm.request", 0.2, phase="interview", operation="next_turn")
    tracker.record("llm.request", 0.4, phase="interview", operation="next_turn")
    tracker.record(
        "tts.playback",
        0.1,
        phase="interview",
        status="interrupted",
    )

    report = tracker.report()

    assert report["models"] == {"llm": "test-model"}
    assert report["summary"] == {
        "llm.request.next_turn": {
            "count": 2,
            "average_ms": 300.0,
            "p50_ms": 200.0,
            "p95_ms": 400.0,
            "max_ms": 400.0,
        }
    }
    assert len(report["events"]) == 3
