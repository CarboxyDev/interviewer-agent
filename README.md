# Interviewer Voice Agent

A consent-first, Python-first voice interviewer that joins Google Meet as a guest and runs an
explicit STT to LLM to TTS cascade. It produces an audio recording, speaker-labelled transcript,
session metadata, and evidence-based notes.

After consent, the agent explains the interview format and asks one focused, verbally answerable
question at a time. The requested duration is a soft target: an answer already in progress can
finish before the agent plays a guaranteed closing statement.

## Safety contract

- The bot joins only a meeting supplied by an authorized host.
- It uses either an anonymous `AI Interviewer` guest or a dedicated Google profile signed in
  manually by the operator.
- It never automates Google credentials, MFA, CAPTCHA, cookies, or account recovery.
- It may send one normal `Ask to join` request and waits for manual host approval.
- It does not repeat admission requests or bypass admission, CAPTCHA, account, or security checks.
- It persists recent join attempts and defaults to three attempts per browser profile per hour.
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

The recommended setup uses a dedicated spare Google account explicitly invited to the Calendar
event. Sign in manually without automating its credentials. The browser desktop is bound to
localhost only:

```bash
docker compose exec interviewer voice-interviewer browser setup
```

Open `http://127.0.0.1:6080/vnc.html?autoconnect=1`, sign in manually, then stop the setup command
with `Ctrl+C`. You may name the dedicated account `AI Interviewer`, but this is optional. Never
copy a personal Chrome profile, inject cookies, or automate password, MFA, CAPTCHA, or Google
security prompts.

Create an interview:

```bash
curl -X POST http://localhost:8000/v1/interviews \
  -F 'meeting_url=https://meet.google.com/abc-defg-hij' \
  -F 'meeting_authorization_confirmed=true' \
  -F 'duration_minutes=15' \
  -F 'resume=@./resume.pdf' \
  -F 'job_description=@./job-description.txt'
```

The host should join first. Prefer a `Trusted` or `Restricted` meeting with the dedicated bot
account explicitly invited. If Meet presents `Ask to join`, the bot sends one request and waits for
manual approval. `Open` access remains a controlled rehearsal fallback. See
[docs/demo-checklist.md](docs/demo-checklist.md).

## Models and configuration

All provider and pipeline choices are environment settings. The default combination prioritizes a
low-cost, responsive demo:

| Stage | Default | Main controls |
| --- | --- | --- |
| STT | `gpt-transcribe` | language, server VAD, context, keywords |
| LLM | `gpt-5.6-luna` | model and reasoning effort |
| TTS | `gpt-4o-mini-tts`, voice `cedar` | model, voice, playback timeout |

Set `INTERVIEWER_REASONING_EFFORT=none` to avoid extra reasoning effort. For experiments, the
default LLM also accepts `low`, `medium`, `high`, `xhigh`, and `max`. Higher effort can improve
deliberation, but usually adds latency and cost. Start with `none`, then compare `low` or `medium`
using the same scripted rehearsal.

The main speech controls are:

- `INTERVIEWER_STT_DELAY`: optional latency control for STT models that support it
- `INTERVIEWER_STT_VAD_THRESHOLD`: speech detection sensitivity from greater than 0 to less than 1
- `INTERVIEWER_STT_PREFIX_PADDING_MS`: audio retained before detected speech
- `INTERVIEWER_STT_SILENCE_DURATION_MS`: silence required to finish a turn
- `INTERVIEWER_STT_CONTEXT_MAX_CHARS`: bounded resume and role context sent to STT, or `0` to disable
- `INTERVIEWER_STT_KEYWORD_LIMIT`: expected terminology sent to STT, or `0` to disable
- `INTERVIEWER_TRANSCRIPT_CLARIFICATION_ATTEMPTS`: repeat requests after clearly unusable text
- `INTERVIEWER_MEET_ATTEMPT_COOLDOWN_SECONDS`: same-link retry cooldown, or `0` to disable
- `INTERVIEWER_MEET_ATTEMPT_HOURLY_LIMIT`: profile-wide hourly limit, or `0` to disable
- `INTERVIEWER_ADMISSION_TIMEOUT_SECONDS`: maximum wait for manual host admission
- `INTERVIEWER_RESPONSE_TIMEOUT_SECONDS`: candidate response window after bot playback
- `INTERVIEWER_CANDIDATE_TURN_TIMEOUT_SECONDS`: maximum active answer duration after speech starts
- `INTERVIEWER_CANDIDATE_TURN_GRACE_SECONDS`: pause allowed between answer segments
- `INTERVIEWER_TTS_TIMEOUT_SECONDS`: independent maximum bot playback time

See `.env.example` for the complete configuration. Model capabilities can change, so verify the
selected values against the official [model catalog](https://developers.openai.com/api/docs/models)
before replacing a default.

The default uses `gpt-transcribe` because the interview loop depends on server-side speech start
and silence detection. Streaming-only models such as `gpt-live-transcribe` need a separate local
turn detector and are not drop-in replacements for this runtime.

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
blocked unless readiness checks pass. Google Meet can refuse an account or guest before admission,
and its DOM can change, so the live demo checklist includes a required feasibility rehearsal.
