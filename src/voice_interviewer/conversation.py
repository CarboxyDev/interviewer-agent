from __future__ import annotations

import re

from voice_interviewer.domain import ConsentDecision, TranscriptionHints

CONSENT_DISCLOSURE = (
    "Hello, I am an AI interviewer. Before we begin, is it okay if I record this conversation "
    "and create a transcript for review? You can withdraw recording consent at any time."
)

CONSENT_DECLINED_CLOSING = (
    "No problem. I will not record anything. Thank you for your time, and you may leave the "
    "meeting whenever you are ready."
)

CONSENT_WITHDRAWAL_CLOSING = (
    "Of course. I have stopped the interview and recording. Thank you for your time, and you may "
    "leave the meeting whenever you are ready."
)

INTERVIEW_CLOSING = (
    "Thank you for your time and for sharing your experience. That concludes the interview. "
    "Your responses have been recorded for review, and you may now leave the meeting."
)

TIME_LIMIT_CLOSING = (
    "We have reached the end of our scheduled time. Thank you for sharing your experience. "
    "That concludes the interview. Your responses have been recorded for review, and you may "
    "now leave the meeting."
)


def interview_opening(duration_minutes: int) -> str:
    return (
        f"Thank you. This interview is planned for about {duration_minutes} minutes. I will begin "
        "with a brief overview, then ask focused questions about your backend experience and "
        "technical decisions. Please ask me to repeat anything that is unclear, and take a moment "
        "to think when needed. To start, please give me a brief overview of your recent backend "
        "work."
    )


DECLINE_PATTERNS = (
    r"\bno\b",
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bdecline\b",
    r"\bnot consent\b",
    r"\bnot (?:okay|ok|fine|comfortable)\b",
    r"\brather not\b",
    r"\b(?:object|refuse)\b",
)
GRANT_PATTERNS = (
    r"\byes\b",
    r"\byeah\b",
    r"\byep\b",
    r"\byup\b",
    r"\bok(?:ay)?\b",
    r"\bi consent\b",
    r"\bi agree\b",
    r"\bthat's fine\b",
    r"\bthat is fine\b",
    r"\bsure\b",
    r"\bgo ahead\b",
    r"\bsounds good\b",
    r"\babsolutely\b",
    r"\bplease do\b",
    r"\bworks for me\b",
    r"\bof course\b",
)
UNCLEAR_PATTERNS = (
    r"\bnot sure\b",
    r"\bmaybe\b",
    r"\buncertain\b",
)
WITHDRAWAL_PATTERNS = (
    r"\bstop (the )?recording\b",
    r"\bstop (the )?interview recording\b",
    r"\bi withdraw (my )?consent\b",
    r"\bdo not record\b",
    r"\bdon't record\b",
    r"\bdelete (the )?(recording|audio|transcript|interview data)\b",
)
INTERVIEW_END_PATTERNS = (
    r"\b(stop|end|conclude|finish) (this|the) interview\b",
    r"\bwrap (this|the) interview up\b",
    r"\bwrap up (this|the) interview\b",
)
INTERVIEW_END_NEGATION_PATTERNS = (
    r"\b(do not|don't|not|never) (stop|end|conclude|finish) (this|the) interview\b",
    r"\b(do not|don't|not|never) wrap (this|the) interview up\b",
    r"\b(do not|don't|not|never) wrap up (this|the) interview\b",
)
PROTECTED_QUESTION_PATTERNS = (
    r"\bhow old\b",
    r"\bwhat is your age\b",
    r"\bare you married\b",
    r"\bdo you have children\b",
    r"\bwhat is your religion\b",
    r"\bwhat is your race\b",
    r"\bwhat is your ethnicity\b",
    r"\bwhat is your sexual orientation\b",
    r"\bdo you have (a )?disabilit",
    r"\bare you pregnant\b",
    r"\bwhat is your citizenship\b",
)
UNCLEAR_TRANSCRIPT_PATTERNS = (
    r"\[(?:inaudible|unintelligible|unclear)\]",
    r"\((?:inaudible|unintelligible|unclear)\)",
    r"\b(?:inaudible|unintelligible)\b",
)
THINKING_REQUEST_PATTERNS = (
    r"let me (?:think|consider that)(?: for a (?:moment|second|minute))?",
    r"(?:just )?give me (?:a )?(?:moment|second|minute)(?: please)?",
    r"(?:can|could) i have (?:a )?(?:moment|second|minute)(?: please)?",
    r"(?:one|a) (?:moment|second|minute)(?: please)?",
    r"i(?:'m| am) thinking",
    r"hold on(?: a (?:moment|second))?",
    r"h+m+",
    r"(?:well|so|basically|actually|i guess|i think|i basically)",
)
REPEAT_REQUEST_PATTERNS = (
    r"(?:sorry )?(?:can|could|would) you (?:please )?repeat(?: that| the question| yourself)?",
    r"(?:please )?repeat(?: that| the question| yourself)?",
    r"(?:sorry )?say that again(?: please)?",
    r"i (?:didn't|did not|couldn't|could not) (?:hear|catch|understand) "
    r"(?:that|the question|you)",
    r"what was the question(?: again)?",
)
CLARIFICATION_REQUEST_PATTERNS = (
    r"(?:what|which) do you mean",
    r"(?:do|did) you mean",
    r"(?:does|would) (?:this|that) include",
    r"(?:work|professional).{0,50}(?:personal|side) project",
    r"(?:personal|side) project.{0,50}(?:work|professional)",
    r"(?:i(?:'m| am) )?not sure i understand (?:what|the question|you(?:'re| are) asking)",
    r"what (?:exactly )?are you asking",
)
INTERVIEW_PUSHBACK_PATTERNS = (
    r"i already (?:told|said|answered|explained)",
    r"as i (?:already )?(?:said|mentioned|explained)",
    r"i just (?:told|said|answered|explained)",
)
OWNERSHIP_BOUNDARY_PATTERNS = (
    r"i (?:did not|didn't) (?:implement|build|change|configure|own|make) (?:this|that|it)",
    r"(?:this|that|it) was not my (?:work|change|implementation|responsibility)",
    r"i only (?:diagnosed|investigated|identified|escalated) (?:this|that|it)",
)
NON_ANSWER_PATTERNS = (
    r"i (?:do not|don't) know",
    r"i(?:'m| am) not sure",
    r"no idea",
    r"i (?:cannot|can't|couldn't|could not) answer",
    r"i have no answer",
    r"nothing (?:useful|specific|really)?",
    r"(?:i )?(?:want to )?pass",
    r"^(?:okay|ok|yeah|yes|no|thanks|thank you|um+|uh+|h+m+)$",
)
KEYWORD_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9.+#/-]{2,49}\b")
KEYWORD_STOP_WORDS = {
    "all",
    "an",
    "about",
    "after",
    "also",
    "and",
    "are",
    "as",
    "at",
    "been",
    "before",
    "build",
    "building",
    "but",
    "by",
    "candidate",
    "description",
    "designed",
    "developed",
    "developer",
    "did",
    "do",
    "engineer",
    "experience",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "into",
    "its",
    "interview",
    "is",
    "job",
    "more",
    "not",
    "of",
    "on",
    "or",
    "our",
    "resume",
    "role",
    "than",
    "that",
    "the",
    "their",
    "they",
    "this",
    "to",
    "using",
    "was",
    "we",
    "were",
    "what",
    "when",
    "which",
    "who",
    "will",
    "with",
    "work",
    "worked",
    "you",
    "your",
    "years",
}


def classify_consent(text: str) -> ConsentDecision:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    if any(re.search(pattern, normalized) for pattern in DECLINE_PATTERNS):
        return ConsentDecision.DECLINED
    if any(re.search(pattern, normalized) for pattern in UNCLEAR_PATTERNS):
        return ConsentDecision.UNCLEAR
    if any(re.search(pattern, normalized) for pattern in GRANT_PATTERNS):
        return ConsentDecision.GRANTED
    return ConsentDecision.UNCLEAR


def is_consent_withdrawal(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    return any(re.search(pattern, normalized) for pattern in WITHDRAWAL_PATTERNS)


def is_interview_end_request(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    if any(re.search(pattern, normalized) for pattern in INTERVIEW_END_NEGATION_PATTERNS):
        return False
    return any(re.search(pattern, normalized) for pattern in INTERVIEW_END_PATTERNS)


def contains_protected_question(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    return any(re.search(pattern, normalized) for pattern in PROTECTED_QUESTION_PATTERNS)


def transcript_needs_clarification(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized or not any(character.isalnum() for character in normalized):
        return True
    lowered = normalized.lower()
    if any(re.search(pattern, lowered) for pattern in UNCLEAR_TRANSCRIPT_PATTERNS):
        return True
    words = re.findall(r"[a-z0-9]+", lowered)
    return any(
        words[index] == words[index + 1] == words[index + 2] == words[index + 3]
        for index in range(max(0, len(words) - 3))
    )


def is_thinking_request(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()
    return any(re.fullmatch(pattern, normalized) for pattern in THINKING_REQUEST_PATTERNS)


def is_repeat_request(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()
    return any(re.fullmatch(pattern, normalized) for pattern in REPEAT_REQUEST_PATTERNS)


def is_clarification_request(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()
    return any(re.search(pattern, normalized) for pattern in CLARIFICATION_REQUEST_PATTERNS)


def is_interview_pushback(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()
    return any(re.search(pattern, normalized) for pattern in INTERVIEW_PUSHBACK_PATTERNS)


def is_ownership_boundary(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()
    return any(re.search(pattern, normalized) for pattern in OWNERSHIP_BOUNDARY_PATTERNS)


def is_non_answer(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9']+", " ", text.lower()).strip()
    if not normalized:
        return True
    if any(re.search(pattern, normalized) for pattern in NON_ANSWER_PATTERNS):
        return True
    return len(re.findall(r"[a-z0-9]+", normalized)) < 3


def repeat_prompt(text: str) -> str:
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text.strip()) if item.strip()]
    final_sentence = sentences[-1] if sentences else text.strip()
    return f"Of course. {final_sentence}"


def build_transcription_hints(
    *,
    resume_text: str,
    job_description_text: str,
    max_chars: int,
    keyword_limit: int,
) -> TranscriptionHints:
    if max_chars <= 0 and keyword_limit <= 0:
        return TranscriptionHints()

    combined = f"{resume_text}\n{job_description_text}"
    keywords = _extract_keywords(combined, keyword_limit)
    prompt = ""
    if max_chars > 0:
        context = _balanced_transcription_context(
            resume_text=resume_text,
            job_description_text=job_description_text,
            max_chars=max_chars,
        )
        prompt = (
            "English backend job interview. Use the supplied role and resume terminology when "
            f"transcribing names and technical terms. Context: {context}"
        )
    return TranscriptionHints(prompt=prompt, keywords=keywords)


def final_question_prompt(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    match = re.search(r"([^.!?]*\?)\s*$", normalized)
    question = match.group(1).strip() if match else f"{normalized.rstrip('.!? ')}?"
    return f"We are nearly out of time, so one final question. {question}"


def _balanced_transcription_context(
    *,
    resume_text: str,
    job_description_text: str,
    max_chars: int,
) -> str:
    resume = re.sub(r"\s+", " ", resume_text).strip()
    role = re.sub(r"\s+", " ", job_description_text).strip()
    if not resume:
        return role[:max_chars]
    if not role:
        return _resume_excerpt(resume, max_chars)

    labels_length = len("Resume:  Role: ")
    content_budget = max(0, max_chars - labels_length)
    resume_budget = round(content_budget * 0.6)
    role_budget = content_budget - resume_budget
    return (f"Resume: {_resume_excerpt(resume, resume_budget)} Role: {role[:role_budget]}")[
        :max_chars
    ]


def _resume_excerpt(resume: str, max_chars: int) -> str:
    if len(resume) <= max_chars:
        return resume
    experience = re.search(r"\bEXPERIENCE\b", resume)
    if experience is None:
        experience = re.search(r"\bexperience\b", resume, re.IGNORECASE)
    if experience is None:
        return resume[:max_chars]
    return resume[experience.start() : experience.start() + max_chars]


def _extract_keywords(text: str, limit: int) -> tuple[str, ...]:
    if limit <= 0:
        return ()
    original_by_normalized: dict[str, str] = {}
    counts: dict[str, int] = {}
    first_positions: dict[str, int] = {}
    for position, match in enumerate(KEYWORD_PATTERN.finditer(text)):
        token = match.group(0).strip("./-")
        normalized = token.casefold()
        if not token or normalized in KEYWORD_STOP_WORDS:
            continue
        original_by_normalized.setdefault(normalized, token)
        first_positions.setdefault(normalized, position)
        counts[normalized] = counts.get(normalized, 0) + 1
    ranked = sorted(counts, key=lambda item: (-counts[item], first_positions[item]))
    return tuple(original_by_normalized[item] for item in ranked[:limit])
