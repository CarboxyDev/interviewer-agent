from voice_interviewer.domain import SpeechEventKind
from voice_interviewer.openai_adapters import _speech_event_from_realtime_event


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
