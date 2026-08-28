# Interviewer Voice Agent

A consent-first, Python-first voice interviewer that joins Google Meet as a guest and runs an
explicit STT to LLM to TTS cascade. It produces an audio recording, speaker-labelled transcript,
session metadata, and evidence-based notes.

## Safety contract

- The bot joins only a meeting supplied by an authorized host.
- It uses a guest identity named `AI Interviewer`. It never signs into Google.
- It does not bypass admission, CAPTCHA, account, or security checks.
- It records only after the candidate explicitly consents in the meeting.
- It does not score candidates or make hiring recommendations.
- It asks no questions about protected personal characteristics.

## Quick start

Requirements: Docker Desktop, an OpenAI API key, and a fresh Google Meet owned by you.

```bash
cp .env.example .env
# Add OPENAI_API_KEY to .env
docker compose build
docker compose up -d
docker compose exec interviewer voice-interviewer doctor --live
```

Create an interview:

```bash
curl -X POST http://localhost:8000/v1/interviews \
  -F 'meeting_url=https://meet.google.com/abc-defg-hij' \
  -F 'meeting_authorization_confirmed=true' \
  -F 'duration_minutes=15' \
  -F 'resume=@./resume.pdf' \
  -F 'job_description=@./job-description.txt'
```

The host must join first and set meeting access to `Open`. Do not admit the bot through an
`Ask to join` flow. See [docs/demo-checklist.md](docs/demo-checklist.md).

## Local development

```bash
uv sync --all-groups
uv run playwright install chromium
uv run alembic upgrade head
uv run voice-interviewer doctor
uv run voice-interviewer serve
```

Run quality checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

API documentation is available at `http://localhost:8000/docs` while the service runs. This is
developer documentation, not a custom product UI.

## Current implementation boundary

The domain, API, CLI, persistence, document extraction, safe Meet admission, provider contracts,
and Docker audio environment are implemented independently. A real interview is deliberately
blocked unless readiness checks pass. Google Meet DOM changes can require selector maintenance,
so the live demo checklist includes a required feasibility rehearsal.
