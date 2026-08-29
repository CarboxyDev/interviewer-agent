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

Requirements: Docker Desktop, an OpenAI API key, and a fresh Google Meet owned by you. The Docker
image installs official Google Chrome Stable for its native `amd64` or `arm64` architecture and
controls it through Playwright over a loopback-only CDP endpoint.

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

## Models and configuration

All provider and pipeline choices are environment settings. The default combination prioritizes a
low-cost, responsive demo:

| Stage | Default | Main controls |
| --- | --- | --- |
| STT | `gpt-live-transcribe` | language, transcription delay, VAD, context, keywords |
| LLM | `gpt-5.6-luna` | model and reasoning effort |
| TTS | `gpt-4o-mini-tts`, voice `marin` | model, voice, playback timeout |

Set `INTERVIEWER_REASONING_EFFORT=none` to avoid extra reasoning effort. For experiments, the
default LLM also accepts `low`, `medium`, `high`, `xhigh`, and `max`. Higher effort can improve
deliberation, but usually adds latency and cost. Start with `none`, then compare `low` or `medium`
using the same scripted rehearsal.

The main speech controls are:

- `INTERVIEWER_STT_DELAY`: `minimal`, `low`, `medium`, `high`, or `xhigh`
- `INTERVIEWER_STT_VAD_THRESHOLD`: speech detection sensitivity from greater than 0 to less than 1
- `INTERVIEWER_STT_PREFIX_PADDING_MS`: audio retained before detected speech
- `INTERVIEWER_STT_SILENCE_DURATION_MS`: silence required to finish a turn
- `INTERVIEWER_STT_CONTEXT_MAX_CHARS`: bounded resume and role context sent to STT, or `0` to disable
- `INTERVIEWER_STT_KEYWORD_LIMIT`: expected terminology sent to STT, or `0` to disable
- `INTERVIEWER_TRANSCRIPT_CLARIFICATION_ATTEMPTS`: repeat requests after clearly unusable text
- `INTERVIEWER_RESPONSE_TIMEOUT_SECONDS`: candidate response window after bot playback
- `INTERVIEWER_TTS_TIMEOUT_SECONDS`: independent maximum bot playback time

See `.env.example` for the complete configuration. Model capabilities can change, so verify the
selected values against the official [model catalog](https://developers.openai.com/api/docs/models)
before replacing a default.

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
blocked unless readiness checks pass. Google Meet can refuse an automated guest before admission,
and its DOM can change, so the live demo checklist includes a required feasibility rehearsal.
