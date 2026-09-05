from voice_interviewer.conversation import (
    CONSENT_DISCLOSURE,
    build_transcription_hints,
    classify_consent,
    contains_protected_question,
    final_question_prompt,
    interview_opening,
    is_clarification_request,
    is_consent_withdrawal,
    is_interview_end_request,
    is_interview_pushback,
    is_non_answer,
    is_ownership_boundary,
    is_repeat_request,
    is_thinking_request,
    repeat_prompt,
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


def test_consent_disclosure_does_not_force_yes_or_no_wording() -> None:
    assert "Please say yes or no" not in CONSENT_DISCLOSURE
    assert CONSENT_DISCLOSURE.endswith("You can withdraw recording consent at any time.")


def test_interview_opening_is_brief_and_role_neutral() -> None:
    assert interview_opening() == (
        "Thank you. To begin, please give me a brief overview of your recent work most relevant "
        "to this role."
    )
    assert "backend" not in interview_opening().lower()


def test_decline_wins_over_ambiguous_yes() -> None:
    assert classify_consent("Yes, but no, do not record") is ConsentDecision.DECLINED
    assert classify_consent("I do not consent") is ConsentDecision.DECLINED
    assert classify_consent("Yeah, but I am not comfortable") is ConsentDecision.DECLINED
    assert classify_consent("Okay, but I would rather not") is ConsentDecision.DECLINED


def test_withdrawal_and_protected_question_guards() -> None:
    assert is_consent_withdrawal("Please stop the recording now")
    assert is_consent_withdrawal("Please stop the interview recording")
    assert is_consent_withdrawal("I withdraw my consent")
    assert is_consent_withdrawal("Delete the recording")
    assert not is_consent_withdrawal("Please stop the interview")
    assert not is_consent_withdrawal("Please repeat the question")
    assert contains_protected_question("How old are you?")
    assert contains_protected_question("Are you married?")
    assert not contains_protected_question("How did you design that API?")


def test_interview_end_requests_are_distinct_from_consent_withdrawal() -> None:
    assert is_interview_end_request("Please stop the interview")
    assert is_interview_end_request("Can we end this interview?")
    assert is_interview_end_request("Let us wrap up the interview")
    assert not is_interview_end_request("Please stop the recording")
    assert not is_interview_end_request("Do not stop the interview")


def test_transcription_hints_prioritize_repeated_role_terms_and_are_bounded() -> None:
    hints = build_transcription_hints(
        resume_text="Built FastAPI services with PostgreSQL and Kafka.",
        job_description_text="FastAPI backend using Kafka, Docker, and PostgreSQL.",
        max_chars=80,
        keyword_limit=4,
    )

    assert set(hints.keywords[:3]) == {"FastAPI", "PostgreSQL", "Kafka"}
    assert len(hints.keywords) == 4
    assert "English job interview" in hints.prompt
    assert len(hints.prompt) <= 220


def test_transcription_context_includes_resume_experience_and_role_text() -> None:
    hints = build_transcription_hints(
        resume_text=(
            "Jordan Lee SUMMARY Backend engineer. EXPERIENCE Example Labs Software Engineer "
            "building payment workflows."
        ),
        job_description_text="Backend role using Python APIs and distributed systems.",
        max_chars=100,
        keyword_limit=10,
    )

    assert "Example Labs" in hints.prompt
    assert "Role:" in hints.prompt


def test_final_question_prompt_announces_the_time_boundary() -> None:
    prompt = final_question_prompt(
        "You described the cache diagnosis. What did you personally change?"
    )

    assert prompt == (
        "We are nearly out of time, so one final question. What did you personally change?"
    )


def test_unclear_transcript_detection_is_conservative() -> None:
    assert transcript_needs_clarification("")
    assert transcript_needs_clarification("[inaudible]")
    assert transcript_needs_clarification("the the the the")
    assert not transcript_needs_clarification("Yes")
    assert not transcript_needs_clarification("I used Kafka for event delivery.")


def test_short_thinking_requests_are_not_complete_answers() -> None:
    assert is_thinking_request("Let me think")
    assert is_thinking_request("Give me a moment, please")
    assert is_thinking_request("Could I have a second?")
    assert is_thinking_request("I basically")
    assert not is_thinking_request("Let me think through how I used Kafka for delivery")
    assert not is_thinking_request("I think we used idempotency keys")


def test_non_answer_detection_does_not_reject_substantive_conversational_answers() -> None:
    assert is_non_answer("I don't know")
    assert is_non_answer("Yeah")
    assert is_non_answer("Nothing useful really")
    assert not is_non_answer("Yeah, I built a FastAPI service")
    assert not is_non_answer("I used Kafka")


def test_repeat_requests_are_recognized_and_question_is_replayed_naturally() -> None:
    assert is_repeat_request("Sorry, can you repeat?")
    assert is_repeat_request("I didn't catch that")
    assert not is_repeat_request("I repeated the database query")
    assert repeat_prompt("You mentioned caching. How did invalidation work?") == (
        "Of course. How did invalidation work?"
    )


def test_candidate_clarification_and_pushback_are_recognized() -> None:
    assert is_clarification_request("Do you mean for work or a personal project?")
    assert is_clarification_request("I'm not sure I understand what you're asking.")
    assert not is_clarification_request("I used a personal project to learn FastAPI.")
    assert is_interview_pushback("I already told you that.")
    assert is_interview_pushback("As I mentioned, it was Spring Boot.")
    assert not is_interview_pushback("I already implemented the endpoint.")


def test_candidate_ownership_boundary_is_recognized() -> None:
    assert is_ownership_boundary("So I didn't change this myself, so I can't comment.")
    assert is_ownership_boundary("That was not my implementation.")
    assert not is_ownership_boundary("I implemented the cache change myself.")


# V2-009: vocabulary must come from the selected role, including non-engineering roles.
def test_transcription_hints_do_not_inject_engineering_context() -> None:
    hints = build_transcription_hints(
        resume_text="Prepared budget forecasts and variance reports.",
        job_description_text="Finance analyst responsible for budgeting and forecasting.",
        max_chars=300,
        keyword_limit=10,
    )
    assert "Finance analyst" in hints.prompt
    assert "variance reports" in hints.prompt
    assert "backend" not in hints.prompt.lower()
    assert "role-specific terms" in hints.prompt
