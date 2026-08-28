from __future__ import annotations

import re

from voice_interviewer.domain import ConsentDecision, TranscriptionHints

CONSENT_DISCLOSURE = (
    "Hello, I am an AI interviewer. I would like to conduct this interview and record the audio "
    "and transcript for review. You can stop at any time. Do you explicitly consent to recording "
    "and transcription? Please answer yes or no."
)

DECLINE_PATTERNS = (
    r"\bno\b",
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bdecline\b",
    r"\bnot consent\b",
)
GRANT_PATTERNS = (
    r"\byes\b",
    r"\bi consent\b",
    r"\bi agree\b",
    r"\bthat's fine\b",
    r"\bthat is fine\b",
    r"\bsure\b",
)
UNCLEAR_PATTERNS = (
    r"\bnot sure\b",
    r"\bmaybe\b",
    r"\buncertain\b",
)
WITHDRAWAL_PATTERNS = (
    r"\bstop (the )?recording\b",
    r"\bstop (the )?interview\b",
    r"\bi withdraw (my )?consent\b",
    r"\bdo not record\b",
    r"\bdon't record\b",
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


def build_transcription_hints(
    *,
    resume_text: str,
    job_description_text: str,
    max_chars: int,
    keyword_limit: int,
) -> TranscriptionHints:
    if max_chars <= 0 and keyword_limit <= 0:
        return TranscriptionHints()

    combined = f"{job_description_text}\n{resume_text}"
    keywords = _extract_keywords(combined, keyword_limit)
    prompt = ""
    if max_chars > 0:
        context = re.sub(r"\s+", " ", combined).strip()[:max_chars]
        prompt = (
            "English backend job interview. Use the supplied role and resume terminology when "
            f"transcribing names and technical terms. Context: {context}"
        )
    return TranscriptionHints(prompt=prompt, keywords=keywords)


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
