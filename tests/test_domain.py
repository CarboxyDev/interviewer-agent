import pytest
from pydantic import ValidationError

from voice_interviewer.domain import InterviewNotes, NextTurn, SessionCreate


def test_meet_url_is_validated_and_canonicalized() -> None:
    request = SessionCreate(
        meeting_url="https://meet.google.com/ABC-DEFG-HIJ?authuser=2",
        duration_minutes=15,
        meeting_authorization_confirmed=True,
    )
    assert str(request.meeting_url) == "https://meet.google.com/abc-defg-hij"


def test_interview_duration_defaults_to_30_minutes() -> None:
    request = SessionCreate(
        meeting_url="https://meet.google.com/abc-defg-hij",
        meeting_authorization_confirmed=True,
    )

    assert request.duration_minutes == 30


@pytest.mark.parametrize(
    ("url", "authorized"),
    [
        ("http://meet.google.com/abc-defg-hij", True),
        ("https://example.com/abc-defg-hij", True),
        ("https://meet.google.com/not-a-code", True),
        ("https://meet.google.com/abc-defg-hij", False),
    ],
)
def test_invalid_or_unauthorized_meet_is_rejected(url: str, authorized: bool) -> None:
    with pytest.raises(ValidationError):
        SessionCreate(
            meeting_url=url,
            duration_minutes=15,
            meeting_authorization_confirmed=authorized,
        )


@pytest.mark.parametrize("model", [NextTurn, InterviewNotes])
def test_openai_output_schemas_are_strict(model: type[NextTurn] | type[InterviewNotes]) -> None:
    schema = model.model_json_schema()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
