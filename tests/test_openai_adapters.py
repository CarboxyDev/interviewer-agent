import json
from types import SimpleNamespace
from typing import Any, cast

from voice_interviewer.domain import (
    AnswerQuality,
    NextTurn,
    ResponseMode,
    Speaker,
    SpeechEventKind,
    TranscriptionHints,
    Utterance,
)
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
        say="You mentioned API delivery. What did you build, and how did you test it?",
        rationale="Probe implementation and testing.",
        topic="Backend project",
        answer_quality=AnswerQuality.SUBSTANTIVE,
        response_mode=ResponseMode.FOLLOW_UP,
        should_end=False,
    )
    focused = NextTurn(
        say=(
            "You mentioned owning the API workflow. What was one important backend decision you "
            "personally made?"
        ),
        rationale="Probe one decision.",
        topic="Backend decision",
        answer_quality=AnswerQuality.SUBSTANTIVE,
        response_mode=ResponseMode.FOLLOW_UP,
        should_end=False,
    )

    assert spoken_turn_issue(bundled, latest_answer="I built a payment API.") is not None
    assert spoken_turn_issue(focused, latest_answer="I built a payment API.") is None


def test_spoken_turn_guard_accepts_natural_semicolon_boundary() -> None:
    turn = NextTurn(
        say=(
            "You mentioned database-access services; what did one of those services do for its "
            "callers?"
        ),
        rationale="Probe one concrete responsibility.",
        topic="Database services",
        answer_quality=AnswerQuality.PARTIAL,
        response_mode=ResponseMode.FOLLOW_UP,
        should_end=False,
    )

    assert spoken_turn_issue(turn, latest_answer="I created database services.") is None


def test_spoken_turn_guard_rejects_false_generic_acknowledgment_for_non_answer() -> None:
    generic = NextTurn(
        say="Thanks, that gives me useful context. What database did you use?",
        rationale="Continue the plan.",
        topic="Databases",
        answer_quality=AnswerQuality.SUBSTANTIVE,
        response_mode=ResponseMode.FOLLOW_UP,
        should_end=False,
    )
    recovery = NextTurn(
        say="I did not catch a concrete example there. Could you describe one backend project?",
        rationale="Ask for a usable example.",
        topic="Backend experience",
        answer_quality=AnswerQuality.NON_ANSWER,
        response_mode=ResponseMode.NARROW,
        should_end=False,
    )

    assert spoken_turn_issue(generic, latest_answer="I don't know") is not None
    assert spoken_turn_issue(recovery, latest_answer="I don't know") is None


def test_spoken_turn_guard_rejects_near_duplicate_question() -> None:
    repeated = NextTurn(
        say=(
            "You added a little more context about the service. What was one backend "
            "responsibility you personally owned?"
        ),
        rationale="Probe ownership.",
        topic="Ownership",
        answer_quality=AnswerQuality.PARTIAL,
        response_mode=ResponseMode.NARROW,
        should_end=False,
    )
    changed_angle = NextTurn(
        say="You worked on database access layers. What changed because of your contribution?",
        rationale="Move from ownership to impact.",
        topic="Impact",
        answer_quality=AnswerQuality.PARTIAL,
        response_mode=ResponseMode.CHANGE_TOPIC,
        should_end=False,
    )
    prior = ("Earlier context. What was one backend responsibility you personally owned?",)

    assert (
        spoken_turn_issue(
            repeated,
            latest_answer="I designed access layers.",
            prior_questions=prior,
        )
        is not None
    )
    assert (
        spoken_turn_issue(
            changed_angle,
            latest_answer="I designed access layers.",
            prior_questions=prior,
        )
        is None
    )


async def test_interviewer_repairs_a_bundled_spoken_question() -> None:
    responses = [
        NextTurn(
            say="What did you build, and how did you test it?",
            rationale="Probe implementation and testing.",
            topic="Backend project",
            answer_quality=AnswerQuality.SUBSTANTIVE,
            response_mode=ResponseMode.FOLLOW_UP,
            should_end=False,
        ).model_dump_json(),
        NextTurn(
            say=(
                "You mentioned owning the API workflow. What was one important backend decision "
                "you personally made?"
            ),
            rationale="Probe one decision.",
            topic="Backend decision",
            answer_quality=AnswerQuality.SUBSTANTIVE,
            response_mode=ResponseMode.FOLLOW_UP,
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
        transcript=[Utterance(Speaker.CANDIDATE, "I built a payment API.", 0, 1)],
        seconds_remaining=300,
    )

    assert turn.say.startswith("You mentioned owning the API workflow.")
    assert len(fake_responses.calls) == 2
    assert "REVISION REQUIRED" in fake_responses.calls[1]["input"]


async def test_interviewer_simplifies_a_grounded_bundled_question_without_retry() -> None:
    response = NextTurn(
        say=(
            "You mentioned owning the API workflow. What did you build, and how did you test it?"
        ),
        rationale="Probe implementation and testing.",
        topic="Backend project",
        answer_quality=AnswerQuality.SUBSTANTIVE,
        response_mode=ResponseMode.FOLLOW_UP,
        should_end=False,
    ).model_dump_json()

    class FakeResponses:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def create(self, **kwargs: Any) -> SimpleNamespace:
            self.calls.append(kwargs)
            return SimpleNamespace(output_text=response)

    fake_responses = FakeResponses()
    client = SimpleNamespace(responses=fake_responses)
    interviewer = OpenAIInterviewer(
        cast(Any, client),
        model="test-model",
        reasoning_effort="none",
    )

    turn = await interviewer.next_turn(
        plan="Ask about backend decisions.",
        transcript=[Utterance(Speaker.CANDIDATE, "I built a payment API.", 0, 1)],
        seconds_remaining=300,
    )

    assert turn.say == "You mentioned owning the API workflow. What did you build?"
    assert len(fake_responses.calls) == 1


def test_realtime_transcription_events_are_correlated_and_deduplicated() -> None:
    completed: set[str] = set()
    started = _speech_event_from_realtime_event(
        {
            "type": "input_audio_buffer.speech_started",
            "item_id": "item-1",
            "audio_start_ms": 100,
        },
        completed,
    )
    stopped = _speech_event_from_realtime_event(
        {
            "type": "input_audio_buffer.speech_stopped",
            "item_id": "item-1",
            "audio_end_ms": 1_600,
        },
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
    assert started.audio_offset_ms == 100
    assert stopped is not None
    assert stopped.kind is SpeechEventKind.SPEECH_STOPPED
    assert stopped.audio_offset_ms == 1_600
    assert final is not None
    assert final.kind is SpeechEventKind.FINAL_TRANSCRIPT
    assert final.text == "I built the API."
    assert final.item_id == "item-1"
    assert duplicate is None
