from voice_interviewer.conversation import (
    build_transcription_hints,
    classify_consent,
    contains_protected_question,
    interview_opening,
    is_consent_withdrawal,
    transcript_needs_clarification,
)
from voice_interviewer.domain import ConsentDecision


def test_consent_requires_clear_affirmation() -> None:
    assert classify_consent("Yes, I consent") is ConsentDecision.GRANTED
    assert classify_consent("Sure, that is fine") is ConsentDecision.GRANTED
    assert classify_consent("Yeah, go ahead") is ConsentDecision.GRANTED
    assert classify_consent("Yep, sounds good") is ConsentDecision.GRANTED
    assert classify_consent("Okay, please do") is ConsentDecision.GRANTED
    assert classify_consent("Absolutely") is ConsentDecision.GRANTED
    assert classify_consent("I am not sure") is ConsentDecision.UNCLEAR


def test_interview_opening_uses_the_configured_duration() -> None:
    assert "about 30 minutes" in interview_opening(30)
    assert "about 5 minutes" in interview_opening(5)


def test_decline_wins_over_ambiguous_yes() -> None:
    assert classify_consent("Yes, but no, do not record") is ConsentDecision.DECLINED
    assert classify_consent("I do not consent") is ConsentDecision.DECLINED
    assert classify_consent("Yeah, but I am not comfortable") is ConsentDecision.DECLINED
    assert classify_consent("Okay, but I would rather not") is ConsentDecision.DECLINED


def test_withdrawal_and_protected_question_guards() -> None:
    assert is_consent_withdrawal("Please stop the recording now")
    assert is_consent_withdrawal("I withdraw my consent")
    assert not is_consent_withdrawal("Please repeat the question")
    assert contains_protected_question("How old are you?")
    assert contains_protected_question("Are you married?")
    assert not contains_protected_question("How did you design that API?")


def test_transcription_hints_prioritize_repeated_role_terms_and_are_bounded() -> None:
    hints = build_transcription_hints(
        resume_text="Built FastAPI services with PostgreSQL and Kafka.",
        job_description_text="FastAPI backend using Kafka, Docker, and PostgreSQL.",
        max_chars=80,
        keyword_limit=4,
    )

    assert set(hints.keywords[:3]) == {"FastAPI", "PostgreSQL", "Kafka"}
    assert len(hints.keywords) == 4
    assert "English backend job interview" in hints.prompt
    assert len(hints.prompt) <= 220


def test_unclear_transcript_detection_is_conservative() -> None:
    assert transcript_needs_clarification("")
    assert transcript_needs_clarification("[inaudible]")
    assert transcript_needs_clarification("the the the the")
    assert not transcript_needs_clarification("Yes")
    assert not transcript_needs_clarification("I used Kafka for event delivery.")
