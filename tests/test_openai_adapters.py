import json
from types import SimpleNamespace
from typing import Any, cast

from voice_interviewer.domain import NextTurn, SpeechEventKind, TranscriptionHints
from voice_interviewer.openai_adapters import (
    REALTIME_TRANSCRIPTION_URL,
    OpenAIInterviewer,
    OpenAIRealtimeTranscriber,
    _provider_error,
    _speech_event_from_realtime_event,
    spoken_turn_issue,
)


def make_transcriber(model: str = "gpt-transcribe") -> OpenAIRealtimeTranscriber:
    return OpenAIRealtimeTranscriber(
        "test-key",
        model=model,
        language="en",
        delay="low",
        vad_threshold=0.5,
        prefix_padding_ms=300,
        silence_duration_ms=500,
    )


def test_realtime_uses_transcription_intent_and_server_vad_configuration() -> None:
    update = make_transcriber()._session_update(
        TranscriptionHints(prompt="Backend interview", keywords=("FastAPI",)),
    )
    transcription = update["session"]["audio"]["input"]["transcription"]
    turn_detection = update["session"]["audio"]["input"]["turn_detection"]

    assert REALTIME_TRANSCRIPTION_URL.endswith("?intent=transcription")
    assert transcription == {
        "model": "gpt-transcribe",
        "languages": ["en"],
        "prompt": "Backend interview",
        "keywords": ["FastAPI"],
    }
    assert turn_detection == {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500,
    }


async def test_realtime_configuration_waits_for_both_handshake_events() -> None:
    class FakeSocket:
        def __init__(self) -> None:
            self.events = iter(
                [
                    json.dumps({"type": "session.created"}),
                    json.dumps({"type": "session.updated"}),
                ]
            )
            self.sent: list[str] = []

        async def recv(self) -> str:
            return next(self.events)

        async def send(self, message: str) -> None:
            self.sent.append(message)

    socket = FakeSocket()
    await make_transcriber()._configure_session(socket, None)

    assert len(socket.sent) == 1
    assert json.loads(socket.sent[0])["type"] == "session.update"


def test_provider_error_preserves_safe_detail_and_redacts_keys() -> None:
    error = _provider_error(
        "realtime transcription",
        RuntimeError("invalid model for sk-secret and Bearer token-value"),
    )

    assert "invalid model" in error.detail
    assert "sk-secret" not in error.detail
    assert "token-value" not in error.detail


def test_spoken_turn_guard_rejects_bundled_questions() -> None:
    bundled = NextTurn(
        say="What did you build, and how did you test it?",
        rationale="Probe implementation and testing.",
        topic="Backend project",
        should_end=False,
    )
    focused = NextTurn(
        say="What was one important backend decision you personally made?",
        rationale="Probe one decision.",
        topic="Backend decision",
        should_end=False,
    )

    assert spoken_turn_issue(bundled) is not None
    assert spoken_turn_issue(focused) is None


async def test_interviewer_repairs_a_bundled_spoken_question() -> None:
    responses = [
        NextTurn(
            say="What did you build, and how did you test it?",
            rationale="Probe implementation and testing.",
            topic="Backend project",
            should_end=False,
        ).model_dump_json(),
        NextTurn(
            say="What was one important backend decision you personally made?",
            rationale="Probe one decision.",
            topic="Backend decision",
            should_end=False,
        ).model_dump_json(),
    ]

    class FakeResponses:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def create(self, **kwargs: Any) -> SimpleNamespace:
            self.calls.append(kwargs)
            return SimpleNamespace(output_text=responses.pop(0))

    fake_responses = FakeResponses()
    client = SimpleNamespace(responses=fake_responses)
    interviewer = OpenAIInterviewer(
        cast(Any, client),
        model="test-model",
        reasoning_effort="none",
    )

    turn = await interviewer.next_turn(
        plan="Ask about backend decisions.",
        transcript=[],
        seconds_remaining=300,
    )

    assert turn.say == "What was one important backend decision you personally made?"
    assert len(fake_responses.calls) == 2
    assert "REVISION REQUIRED" in fake_responses.calls[1]["input"]


def test_realtime_transcription_events_are_correlated_and_deduplicated() -> None:
    completed: set[str] = set()
    started = _speech_event_from_realtime_event(
        {"type": "input_audio_buffer.speech_started", "item_id": "item-1"},
        completed,
    )
    final_event = {
        "type": "conversation.item.input_audio_transcription.completed",
        "item_id": "item-1",
        "transcript": "  I built the API.  ",
    }
    final = _speech_event_from_realtime_event(final_event, completed)
    duplicate = _speech_event_from_realtime_event(final_event, completed)

    assert started is not None
    assert started.kind is SpeechEventKind.SPEECH_STARTED
    assert started.item_id == "item-1"
    assert final is not None
    assert final.kind is SpeechEventKind.FINAL_TRANSCRIPT
    assert final.text == "I built the API."
    assert final.item_id == "item-1"
    assert duplicate is None
