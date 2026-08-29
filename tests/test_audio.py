import asyncio
from collections.abc import AsyncIterator

import pytest

from voice_interviewer.audio import PulseAudioRouter
from voice_interviewer.domain import FailureCode
from voice_interviewer.errors import InterviewerError


class FakeStderr:
    def __init__(self, detail: bytes = b"") -> None:
        self.detail = detail

    async def read(self) -> bytes:
        return self.detail


class FakeStdin:
    def __init__(self, process: "FakeProcess", *, block_until_terminated: bool) -> None:
        self.process = process
        self.block_until_terminated = block_until_terminated
        self.drain_started = asyncio.Event()

    def write(self, chunk: bytes) -> None:
        return None

    async def drain(self) -> None:
        self.drain_started.set()
        if self.block_until_terminated:
            await self.process.terminated.wait()
            raise BrokenPipeError

    def can_write_eof(self) -> bool:
        return True

    def write_eof(self) -> None:
        return None


class FakeProcess:
    def __init__(
        self,
        *,
        wait_returncode: int,
        stderr: bytes = b"",
        block_drain_until_terminated: bool = False,
    ) -> None:
        self.returncode: int | None = None
        self.wait_returncode = wait_returncode
        self.terminated = asyncio.Event()
        self.stdin = FakeStdin(self, block_until_terminated=block_drain_until_terminated)
        self.stderr = FakeStderr(stderr)

    async def wait(self) -> int:
        if self.stdin.block_until_terminated:
            await self.terminated.wait()
        self.returncode = self.wait_returncode
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15
        self.terminated.set()

    def kill(self) -> None:
        self.returncode = -9
        self.terminated.set()


async def one_audio_chunk() -> AsyncIterator[bytes]:
    yield b"\x00\x00" * 100


async def test_barge_in_pipe_close_is_expected_playback_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeProcess(wait_returncode=-15, block_drain_until_terminated=True)

    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    router = PulseAudioRouter()

    playback = asyncio.create_task(router.play_bot_audio(one_audio_chunk()))
    await process.stdin.drain_started.wait()
    await router.stop_bot_audio()
    await playback


async def test_unexpected_pacat_exit_remains_audio_device_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = FakeProcess(wait_returncode=1, stderr=b"PulseAudio connection failed")

    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    router = PulseAudioRouter()

    with pytest.raises(InterviewerError) as caught:
        await router.play_bot_audio(one_audio_chunk())

    assert caught.value.code is FailureCode.AUDIO_DEVICE_FAILURE
    assert caught.value.detail == "PulseAudio connection failed"
