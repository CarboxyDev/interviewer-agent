from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from openai import AsyncOpenAI
from playwright.async_api import async_playwright

from voice_interviewer.config import Settings


async def run_checks(settings: Settings, *, live: bool = False) -> dict[str, object]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    checks: dict[str, object] = {
        "openai_api_key": bool(settings.openai_api_key),
        "data_directory": _writable(settings.data_dir),
        "chromium": await _chromium_available(headless=settings.headless),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "pulseaudio_tools": all(shutil.which(command) for command in ("pactl", "parec", "pacat")),
    }
    checks["audio_sinks"] = await _audio_sinks_available()
    if live and settings.openai_api_key:
        checks["openai_models"] = await _models_available(settings)
    return checks


def is_ready(checks: dict[str, object]) -> bool:
    return all(value is True for value in checks.values())


def _writable(path: Path) -> bool:
    return path.exists() and path.is_dir() and bool(path.stat().st_mode & 0o200)


async def _audio_sinks_available() -> bool:
    if shutil.which("pactl") is None:
        return False
    try:
        process = await asyncio.create_subprocess_exec(
            "pactl",
            "list",
            "short",
            "sinks",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        output, _ = await asyncio.wait_for(process.communicate(), timeout=3)
    except (OSError, TimeoutError):
        return False
    text = output.decode("utf-8", errors="replace")
    return process.returncode == 0 and "meet_output" in text and "bot_microphone" in text


async def _chromium_available(*, headless: bool) -> bool:
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            await browser.close()
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
