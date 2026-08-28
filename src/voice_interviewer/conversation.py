from __future__ import annotations

import re

from voice_interviewer.domain import ConsentDecision

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
