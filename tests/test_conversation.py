from voice_interviewer.conversation import (
    classify_consent,
    contains_protected_question,
    is_consent_withdrawal,
)
from voice_interviewer.domain import ConsentDecision


def test_consent_requires_clear_affirmation() -> None:
    assert classify_consent("Yes, I consent") is ConsentDecision.GRANTED
    assert classify_consent("Sure, that is fine") is ConsentDecision.GRANTED
    assert classify_consent("I am not sure") is ConsentDecision.UNCLEAR


def test_decline_wins_over_ambiguous_yes() -> None:
    assert classify_consent("Yes, but no, do not record") is ConsentDecision.DECLINED
    assert classify_consent("I do not consent") is ConsentDecision.DECLINED


def test_withdrawal_and_protected_question_guards() -> None:
    assert is_consent_withdrawal("Please stop the recording now")
    assert is_consent_withdrawal("I withdraw my consent")
    assert not is_consent_withdrawal("Please repeat the question")
    assert contains_protected_question("How old are you?")
    assert contains_protected_question("Are you married?")
    assert not contains_protected_question("How did you design that API?")
