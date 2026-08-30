from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import httpx
import typer
import uvicorn

from voice_interviewer.api import create_app
from voice_interviewer.config import Settings
from voice_interviewer.doctor import is_ready, run_checks
from voice_interviewer.meet import PlaywrightMeetTransport

app = typer.Typer(no_args_is_help=True, help="Consent-first Google Meet interviewer")
interview_app = typer.Typer(no_args_is_help=True)
browser_app = typer.Typer(no_args_is_help=True)
app.add_typer(interview_app, name="interview")
app.add_typer(browser_app, name="browser")


@app.command()
def serve() -> None:
    """Run the FastAPI service."""
    settings = Settings()
    uvicorn.run(
        create_app(),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


@app.command()
def doctor(
    live: Annotated[
        bool,
        typer.Option(help="Also verify configured model access with OpenAI"),
    ] = False,
) -> None:
    """Check local runtime dependencies without starting an interview."""
    checks = asyncio.run(run_checks(Settings(), live=live))
    for name, passed in checks.items():
        typer.echo(f"{'OK' if passed is True else 'FAIL'}  {name}")
    if not is_ready(checks):
        raise typer.Exit(1)


@browser_app.command("setup")
def setup_browser_profile() -> None:
    """Open the dedicated Chrome profile for a manual Google sign-in."""
    asyncio.run(_setup_browser_profile(Settings()))


@interview_app.command("start")
def start_interview(
    meeting_url: Annotated[str, typer.Option()],
    resume: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    job_description: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    authorized: Annotated[
        bool,
        typer.Option(help="Confirm the meeting owner authorized the bot"),
    ] = False,
    duration_minutes: Annotated[int, typer.Option(min=5, max=45)] = 30,
    server: Annotated[str, typer.Option()] = "http://127.0.0.1:8000",
) -> None:
    """Submit a new interview to the running service."""
    if not authorized:
        typer.echo("Refusing to start without --authorized", err=True)
        raise typer.Exit(2)
    with resume.open("rb") as resume_file, job_description.open("rb") as job_file:
        response = httpx.post(
            f"{server}/v1/interviews",
            data={
                "meeting_url": meeting_url,
                "meeting_authorization_confirmed": "true",
                "duration_minutes": str(duration_minutes),
            },
            files={
                "resume": (resume.name, resume_file),
                "job_description": (job_description.name, job_file),
            },
            timeout=30,
        )
    _show_response(response)


@interview_app.command("status")
def interview_status(
    session_id: str,
    server: Annotated[str, typer.Option()] = "http://127.0.0.1:8000",
) -> None:
    _show_response(httpx.get(f"{server}/v1/interviews/{session_id}", timeout=10))


@interview_app.command("stop")
def stop_interview(
    session_id: str,
    server: Annotated[str, typer.Option()] = "http://127.0.0.1:8000",
) -> None:
    _show_response(httpx.post(f"{server}/v1/interviews/{session_id}/stop", timeout=15))


@interview_app.command("download")
def download_artifacts(
    session_id: str,
    output: Annotated[Path, typer.Option()] = Path("interview-artifacts.zip"),
    server: Annotated[str, typer.Option()] = "http://127.0.0.1:8000",
) -> None:
    response = httpx.get(f"{server}/v1/interviews/{session_id}/artifacts.zip", timeout=30)
    if response.is_error:
        _show_response(response)
    output.write_bytes(response.content)
    typer.echo(str(output.resolve()))


@interview_app.command("delete")
def delete_interview(
    session_id: str,
    server: Annotated[str, typer.Option()] = "http://127.0.0.1:8000",
) -> None:
    response = httpx.delete(f"{server}/v1/interviews/{session_id}", timeout=15)
    if response.is_error:
        _show_response(response)
    typer.echo("Deleted")


def _show_response(response: httpx.Response) -> None:
    if response.is_error:
        typer.echo(response.text, err=True)
        raise typer.Exit(1)
    if response.content:
        typer.echo(json.dumps(response.json(), indent=2))


async def _setup_browser_profile(settings: Settings) -> None:
    transport = PlaywrightMeetTransport(
        headless=False,
        profile_dir=settings.browser_profile_dir,
        connection_mode=settings.browser_connection_mode,
        cdp_port=settings.browser_cdp_port,
        browser_channel=settings.browser_channel,
        browser_executable_path=settings.browser_executable_path,
    )
    try:
        await transport.open_profile_setup()
        typer.echo("Chrome is ready at http://127.0.0.1:6080/vnc.html?autoconnect=1")
        typer.echo("Sign in manually, then press Ctrl+C in this terminal.")
        await asyncio.Event().wait()
    finally:
        await transport.leave()


if __name__ == "__main__":
    app()
