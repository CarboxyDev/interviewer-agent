from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import suppress
from typing import Any, cast
from urllib.parse import quote

import websockets
from openai import AsyncOpenAI, OpenAIError

from voice_interviewer.conversation import contains_protected_question
from voice_interviewer.domain import (
    FailureCode,
    InterviewNotes,
    NextTurn,
    SpeechEvent,
    SpeechEventKind,
    Utterance,
)
from voice_interviewer.errors import InterviewerError

INTERVIEWER_POLICY = """You are a professional AI interviewer conducting an English interview.
Ask exactly one concise question at a time. Adapt questions to the candidate's resume, the job
description, and earlier answers. Prefer evidence-seeking follow-ups over trivia. Cover experience,
technical depth, decisions, tradeoffs, and realistic scenarios. Never ask about age, family status,
health, religion, race, ethnicity, sexuality, disability, citizenship, or any other protected
personal characteristic. Never score the candidate or make a hiring recommendation. Do not claim
facts that are absent from the supplied context. Keep spoken turns under 70 words. Close politely
when time is nearly exhausted."""


class OpenAIInterviewer:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str,
        reasoning_effort: str,
    ) -> None:
        self.client = client
        self.model = model
        self.reasoning_effort = reasoning_effort

    async def prepare(
        self,
        *,
        resume_text: str,
        job_description_text: str,
        duration_minutes: int,
    ) -> str:
        prompt = (
            f"Create a compact interview plan for a {duration_minutes}-minute interview. "
            "Identify role competencies, relevant resume evidence, and a flexible sequence of "
            "topics. Do not write a rigid script.\n\n"
            f"JOB DESCRIPTION\n{job_description_text[:50_000]}\n\n"
            f"RESUME\n{resume_text[:50_000]}"
        )
        try:
            response = await self.client.responses.create(
                model=self.model,
                instructions=INTERVIEWER_POLICY,
                input=prompt,
                reasoning=cast(Any, {"effort": self.reasoning_effort}),
                store=False,
            )
        except OpenAIError as exc:
            raise _provider_error("interview planning", exc) from exc
        return response.output_text.strip()

    async def next_turn(
        self,
        *,
        plan: str,
        transcript: Sequence[Utterance],
        seconds_remaining: int,
    ) -> NextTurn:
        history = [{"speaker": item.speaker.value, "text": item.text} for item in transcript[-20:]]
        try:
            response = await self.client.responses.create(
                model=self.model,
                instructions=INTERVIEWER_POLICY,
                input=(
                    f"INTERVIEW PLAN\n{plan}\n\n"
                    f"SECONDS REMAINING\n{seconds_remaining}\n\n"
                    f"TRANSCRIPT\n{json.dumps(history, ensure_ascii=False)}\n\n"
                    "Choose the next spoken turn. Set should_end true only when closing the "
                    "interview."
                ),
                reasoning=cast(Any, {"effort": self.reasoning_effort}),
                text=cast(
                    Any,
                    {
                        "format": {
                            "type": "json_schema",
                            "name": "next_interview_turn",
                            "schema": NextTurn.model_json_schema(),
                            "strict": True,
                        }
                    },
                ),
                store=False,
            )
        except OpenAIError as exc:
            raise _provider_error("question generation", exc) from exc
        turn = NextTurn.model_validate_json(response.output_text)
        if contains_protected_question(turn.say):
            raise InterviewerError(
                FailureCode.INTERNAL_ERROR,
                "Generated question violated the interview safety policy",
            )
        return turn

    async def notes(self, transcript: Sequence[Utterance]) -> InterviewNotes:
        history = [{"speaker": item.speaker.value, "text": item.text} for item in transcript]
        try:
            response = await self.client.responses.create(
                model=self.model,
                instructions=(
                    "Create neutral, evidence-based interview notes. Do not score, rank, infer "
                    "protected traits, or make a hiring recommendation. State uncertainty and do "
                    "not add facts."
                ),
                input=json.dumps(history, ensure_ascii=False),
                reasoning=cast(Any, {"effort": self.reasoning_effort}),
                text=cast(
                    Any,
                    {
                        "format": {
                            "type": "json_schema",
                            "name": "interview_notes",
                            "schema": InterviewNotes.model_json_schema(),
                            "strict": True,
                        }
                    },
                ),
                store=False,
            )
        except OpenAIError as exc:
            raise _provider_error("note generation", exc) from exc
        return InterviewNotes.model_validate_json(response.output_text)


class OpenAITextToSpeech:
    def __init__(self, client: AsyncOpenAI, *, model: str, voice: str) -> None:
        self.client = client
        self.model = model
        self.voice = voice

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        try:
            async with self.client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=cast(Any, self.voice),
                input=text,
                instructions="Speak warmly, clearly, and at a natural interview pace.",
                response_format="pcm",
            ) as response:
                async for chunk in response.iter_bytes(chunk_size=4_800):
                    yield chunk
        except OpenAIError as exc:
            raise _provider_error("speech synthesis", exc) from exc


class OpenAIRealtimeTranscriber:
    """Streams mono 24 kHz signed 16-bit little-endian PCM to transcription mode."""

    def __init__(self, api_key: str, *, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def transcribe(self, audio: AsyncIterator[bytes]) -> AsyncIterator[SpeechEvent]:
        url = f"wss://api.openai.com/v1/realtime?model={quote(self.model)}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with websockets.connect(url, additional_headers=headers) as socket:
                await socket.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {
                                "type": "transcription",
                                "audio": {
                                    "input": {
                                        "format": {"type": "audio/pcm", "rate": 24_000},
                                        "transcription": {
                                            "model": self.model,
                                            "languages": ["en"],
                                            "delay": "low",
                                        },
                                        "turn_detection": {
                                            "type": "server_vad",
                                            "threshold": 0.5,
                                            "prefix_padding_ms": 300,
                                            "silence_duration_ms": 500,
                                        },
                                    },
                                },
                            },
                        }
                    )
                )
                producer = asyncio.create_task(self._send_audio(socket, audio))
                try:
                    async for raw in socket:
                        event = json.loads(raw)
                        event_type = event.get("type")
                        if event_type == "input_audio_buffer.speech_started":
                            yield SpeechEvent(SpeechEventKind.SPEECH_STARTED)
                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            transcript = str(event.get("transcript", "")).strip()
                            if transcript:
                                yield SpeechEvent(SpeechEventKind.FINAL_TRANSCRIPT, transcript)
                        elif event_type == "error":
                            message = event.get("error", {}).get(
                                "message",
                                "Unknown transcription error",
                            )
                            raise RuntimeError(message)
                finally:
                    producer.cancel()
                    with suppress(asyncio.CancelledError):
                        await producer
        except InterviewerError:
            raise
        except Exception as exc:
            raise _provider_error("realtime transcription", exc) from exc

    @staticmethod
    async def _send_audio(socket: Any, audio: AsyncIterator[bytes]) -> None:
        async for chunk in audio:
            await socket.send(
                json.dumps(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(chunk).decode("ascii"),
                    }
                )
            )


def _provider_error(operation: str, exc: Exception) -> InterviewerError:
    return InterviewerError(
        FailureCode.OPENAI_UNAVAILABLE,
        f"OpenAI {operation} failed ({type(exc).__name__})",
    )
