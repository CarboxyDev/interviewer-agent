from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI

from voice_interviewer.artifacts import FilesystemArtifactStore
from voice_interviewer.audio import PulseAudioRouter
from voice_interviewer.config import Settings
from voice_interviewer.domain import FailureCode
from voice_interviewer.meet import MeetingAttemptLimiter, PlaywrightMeetTransport
from voice_interviewer.openai_adapters import (
    OpenAIInterviewer,
    OpenAIRealtimeTranscriber,
    OpenAITextToSpeech,
)
from voice_interviewer.persistence import SqlAlchemySessionRepository
from voice_interviewer.ports import InterviewRunner
from voice_interviewer.runner import ConversationRunner
from voice_interviewer.service import InterviewService


class UnconfiguredRunner:
    def __init__(self, repository: SqlAlchemySessionRepository) -> None:
        self.repository = repository

    async def run(self, session_id: str) -> None:
        await self.repository.fail(
            session_id,
            FailureCode.OPENAI_UNAVAILABLE,
            "OPENAI_API_KEY is not configured",
        )

    async def stop(self, session_id: str) -> None:
        return None


@dataclass(slots=True)
class Runtime:
    settings: Settings
    repository: SqlAlchemySessionRepository
    artifacts: FilesystemArtifactStore
    service: InterviewService
    openai_client: AsyncOpenAI | None

    async def initialize(self) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        await self.repository.initialize()
        await self.repository.fail_interrupted()

    async def close(self) -> None:
        if self.openai_client is not None:
            await self.openai_client.close()
        await self.repository.close()


def build_runtime(settings: Settings | None = None) -> Runtime:
    configured = settings or Settings()
    repository = SqlAlchemySessionRepository(configured.database_url)
    artifacts = FilesystemArtifactStore(configured.artifacts_dir)
    client: AsyncOpenAI | None = None
    runner: InterviewRunner
    if configured.openai_api_key:
        client = AsyncOpenAI(api_key=configured.openai_api_key)
        runner = ConversationRunner(
            repository=repository,
            artifacts=artifacts,
            meet=PlaywrightMeetTransport(
                headless=configured.headless,
                profile_dir=configured.browser_profile_dir,
                connection_mode=configured.browser_connection_mode,
                cdp_port=configured.browser_cdp_port,
                browser_channel=configured.browser_channel,
                browser_executable_path=configured.browser_executable_path,
                limiter=MeetingAttemptLimiter(
                    cooldown_seconds=configured.meet_attempt_cooldown_seconds,
                    hourly_limit=configured.meet_attempt_hourly_limit,
                    state_path=configured.browser_profile_dir.parent / "meet-attempts.json",
                ),
            ),
            audio=PulseAudioRouter(),
            stt=OpenAIRealtimeTranscriber(
                configured.openai_api_key,
                model=configured.stt_model,
                language=configured.stt_language,
                delay=configured.stt_delay,
                vad_threshold=configured.stt_vad_threshold,
                prefix_padding_ms=configured.stt_prefix_padding_ms,
                silence_duration_ms=configured.stt_silence_duration_ms,
            ),
            interviewer=OpenAIInterviewer(
                client,
                model=configured.llm_model,
                reasoning_effort=configured.reasoning_effort,
            ),
            tts=OpenAITextToSpeech(
                client,
                model=configured.tts_model,
                voice=configured.tts_voice,
            ),
            admission_timeout_seconds=configured.admission_timeout_seconds,
            participant_timeout_seconds=configured.participant_timeout_seconds,
            consent_timeout_seconds=configured.consent_timeout_seconds,
            response_timeout_seconds=configured.response_timeout_seconds,
            candidate_turn_timeout_seconds=configured.candidate_turn_timeout_seconds,
            candidate_turn_grace_seconds=configured.candidate_turn_grace_seconds,
            tts_timeout_seconds=configured.tts_timeout_seconds,
            stt_context_max_chars=configured.stt_context_max_chars,
            stt_keyword_limit=configured.stt_keyword_limit,
            transcript_clarification_attempts=configured.transcript_clarification_attempts,
        )
    else:
        runner = UnconfiguredRunner(repository)
    service = InterviewService(
        repository=repository,
        artifacts=artifacts,
        runner=runner,
        maximum_upload_bytes=configured.maximum_upload_bytes,
    )
    return Runtime(configured, repository, artifacts, service, client)
