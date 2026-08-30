from __future__ import annotations

from voice_interviewer.domain import FailureCode


class InterviewerError(Exception):
    """Base error carrying a stable public failure code."""

    def __init__(self, code: FailureCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class InvalidTransitionError(ValueError):
    pass


class SessionNotFoundError(LookupError):
    pass


class ActiveSessionError(RuntimeError):
    pass


class DocumentError(ValueError):
    pass


class ConsentWithdrawnError(RuntimeError):
    pass


class ParticipantLeftError(RuntimeError):
    pass
