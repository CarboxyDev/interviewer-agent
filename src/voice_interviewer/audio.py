from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path

from voice_interviewer.domain import FailureCode
from voice_interviewer.errors import InterviewerError


class PulseAudioRouter:
    """Routes 24 kHz mono PCM between PulseAudio, Chromium, OpenAI, and FFmpeg."""

    def __init__(self) -> None:
        self._playback: asyncio.subprocess.Process | None = None
        self._capture: asyncio.subprocess.Process | None = None
        self._recorder: asyncio.subprocess.Process | None = None

    async def candidate_audio(self) -> AsyncIterator[bytes]:
        self._capture = await asyncio.create_subprocess_exec(
            "parec",
            "--device=meet_output.monitor",
            "--format=s16le",
            "--rate=24000",
            "--channels=1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if self._capture.stdout is None:
            raise InterviewerError(FailureCode.AUDIO_DEVICE_FAILURE, "parec has no output stream")
        try:
            while chunk := await self._capture.stdout.read(4_800):
                yield chunk
            error = await self._read_error(self._capture)
            if error:
                raise InterviewerError(FailureCode.AUDIO_DEVICE_FAILURE, error)
        finally:
            await self._terminate(self._capture)
            self._capture = None

    async def play_bot_audio(self, audio: AsyncIterator[bytes]) -> None:
        await self.stop_bot_audio()
        process = await asyncio.create_subprocess_exec(
            "pacat",
            "--device=bot_microphone",
            "--format=s16le",
            "--rate=24000",
            "--channels=1",
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._playback = process
        if process.stdin is None:
            raise InterviewerError(FailureCode.AUDIO_DEVICE_FAILURE, "pacat has no input stream")
        try:
            async for chunk in audio:
                if process.returncode is not None:
                    break
                try:
                    process.stdin.write(chunk)
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    break
                except RuntimeError:
                    if self._playback is not process:
                        break
                    raise
            if process.returncode is None and process.stdin.can_write_eof():
                try:
                    process.stdin.write_eof()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except RuntimeError:
                    if self._playback is process:
                        raise
            await process.wait()
            error = await self._read_error(process)
            if process.returncode and self._playback is process:
                detail = error or f"pacat exited with code {process.returncode}"
                raise InterviewerError(FailureCode.AUDIO_DEVICE_FAILURE, detail)
        finally:
            if self._playback is process:
                self._playback = None

    async def stop_bot_audio(self) -> None:
        process = self._playback
        self._playback = None
        if process is not None:
            await self._terminate(process)

    async def start_recording(self, session_dir: Path) -> None:
        await asyncio.to_thread(session_dir.mkdir, parents=True, exist_ok=True)
        output = session_dir / "interview.mp3"
        self._recorder = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "pulse",
            "-i",
            "meet_output.monitor",
            "-f",
            "pulse",
            "-i",
            "bot_microphone.monitor",
            "-filter_complex",
            "amix=inputs=2:duration=longest:normalize=0",
            "-ac",
            "1",
            "-ar",
            "24000",
            str(output),
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.sleep(0.25)
        if self._recorder.returncode is not None:
            error = await self._read_error(self._recorder)
            self._recorder = None
            raise InterviewerError(FailureCode.AUDIO_DEVICE_FAILURE, error or "FFmpeg exited")

    async def stop_recording(self) -> Path | None:
        if self._recorder is None:
            return None
        process = self._recorder
        self._recorder = None
        if process.stdin is not None and process.returncode is None:
            process.stdin.write(b"q\n")
            await process.stdin.drain()
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except TimeoutError:
            await self._terminate(process)
        return None

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        with suppress(TimeoutError):
            await asyncio.wait_for(process.wait(), timeout=3)
        if process.returncode is None:
            process.kill()
            await process.wait()

    @staticmethod
    async def _read_error(process: asyncio.subprocess.Process) -> str:
        if process.stderr is None:
            return ""
        return (await process.stderr.read()).decode("utf-8", errors="replace").strip()[:500]
