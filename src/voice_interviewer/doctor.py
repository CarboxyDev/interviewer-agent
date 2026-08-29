from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from openai import AsyncOpenAI

from voice_interviewer.config import Settings
from voice_interviewer.meet import PlaywrightMeetTransport


async def run_checks(settings: Settings, *, live: bool = False) -> dict[str, object]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
    checks: dict[str, object] = {
        "openai_api_key": bool(settings.openai_api_key),
        "data_directory": _writable(settings.data_dir),
        "browser_profile_directory": _writable(settings.browser_profile_dir),
        "browser": await _browser_available(settings),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "pulseaudio_tools": all(shutil.which(command) for command in ("pactl", "parec", "pacat")),
    }
    checks["audio_devices"] = await _audio_devices_available()
    if live and settings.openai_api_key:
        checks["openai_models"] = await _models_available(settings)
    return checks


def is_ready(checks: dict[str, object]) -> bool:
    return all(value is True for value in checks.values())


def _writable(path: Path) -> bool:
    return path.exists() and path.is_dir() and bool(path.stat().st_mode & 0o200)


async def _audio_devices_available() -> bool:
    if shutil.which("pactl") is None:
        return False
    try:
        sinks_process = await asyncio.create_subprocess_exec(
            "pactl",
            "list",
            "short",
            "sinks",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        sources_process = await asyncio.create_subprocess_exec(
            "pactl",
            "list",
            "short",
            "sources",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        (sinks_output, _), (sources_output, _) = await asyncio.wait_for(
            asyncio.gather(sinks_process.communicate(), sources_process.communicate()),
            timeout=3,
        )
    except (OSError, TimeoutError):
        return False
    sinks = sinks_output.decode("utf-8", errors="replace")
    sources = sources_output.decode("utf-8", errors="replace")
    return (
        sinks_process.returncode == 0
        and sources_process.returncode == 0
        and "meet_output" in sinks
        and "bot_microphone" in sinks
        and "meet_output.monitor" in sources
        and "bot_microphone_source" in sources
    )


async def _browser_available(settings: Settings) -> bool:
    transport = PlaywrightMeetTransport(
        headless=settings.headless,
        profile_dir=settings.browser_profile_dir / "doctor",
        connection_mode=settings.browser_connection_mode,
        cdp_port=settings.browser_cdp_port,
        browser_channel=settings.browser_channel,
        browser_executable_path=settings.browser_executable_path,
    )
    try:
        await transport.probe()
        return True
    except Exception:
        return False


async def _models_available(settings: Settings) -> bool:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        await asyncio.gather(
            client.models.retrieve(settings.stt_model),
            client.models.retrieve(settings.llm_model),
            client.models.retrieve(settings.tts_model),
        )
        return True
    except Exception:
        return False
    finally:
        await client.close()
