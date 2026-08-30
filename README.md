# Interviewer Voice Agent

[![CI](https://github.com/CarboxyDev/interviewer-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/CarboxyDev/interviewer-agent/actions/workflows/ci.yml)

An AI voice interviewer that joins an authorized Google Meet through a dedicated, manually
signed-in bot account. It uses a cascading speech-to-text, LLM, and text-to-speech pipeline to run
adaptive interviews and produce a recording, speaker-labelled transcript, latency metrics, and
evidence-based notes.

## Reviewer guide

Run the complete quality gate without Google or OpenAI credentials:

```bash
uv sync --all-groups
make check
```

The project uses an async modular monolith with explicit ports for Meet, audio, transcription,
interview generation, persistence, and artifacts. This keeps the interview behavior testable
without browser automation, audio devices, or paid API calls.

Useful review documents:

- [Architecture](docs/architecture.md): module boundaries, audio topology, and state machine
- [Product requirements](docs/PRD.md): scope, behavior, non-goals, and acceptance criteria
- [Configuration](docs/configuration.md): environment settings and operational controls
- [SQLite decision](docs/decisions/0001-sqlite-for-local-v1.md): persistence rationale

## Repository map

| Area | Responsibility |
| --- | --- |
| `service.py` | Validates requests, persists inputs, and starts one interview session |
| `runner.py` | Orchestrates preparation, Meet, consent, conversation, and finalization |
| `conversation.py` | Builds transcription hints and deterministic conversation guards |
| `meet.py` and `audio.py` | Control the signed-in Meet participant and isolated audio paths |
| `openai_adapters.py` | Implements STT, interviewer, and TTS provider adapters |
| `persistence.py` and `artifacts.py` | Store session state and consented outputs |
| `api.py` and `cli.py` | Provide local control surfaces |

## Quick start

Requirements: Docker Desktop, an OpenAI API key, a dedicated Google bot account, and an authorized
Google Meet.

```bash
cp .env.example .env
# Add OPENAI_API_KEY to .env
docker compose build
docker compose up -d
docker compose exec interviewer voice-interviewer browser setup
```

Open `http://127.0.0.1:6080/vnc.html?autoconnect=1`, sign in to the dedicated bot account manually,
then stop the setup command with `Ctrl+C`. The application never automates the account password,
MFA, CAPTCHA, recovery flow, or cookie injection.

Check the runtime and start an interview through the CLI:

```bash
docker compose exec interviewer voice-interviewer doctor --live

docker compose exec interviewer voice-interviewer interview start \
  --meeting-url 'https://meet.google.com/abc-defg-hij' \
  --resume /input/resume.pdf \
  --job-description /input/backend-job-description.txt \
  --duration-minutes 15 \
  --authorized
```

Place the referenced input files in the local `input/` directory before starting. The CLI also
supports status, stop, download, metrics, and deletion commands. The same capabilities are exposed
through the local FastAPI routes documented at `http://127.0.0.1:8000/docs`.

## Safety contract

- The bot uses a manually signed-in dedicated account; anonymous joining is rejected.
- It joins only authorized meetings and never automates credentials or bypasses Google security.
- It records only after explicit consent; withdrawing consent deletes the recorded content.
- It never produces a candidate score or hiring recommendation.

## Storage and retrieval

SQLite stores session state in `data/interviewer.db`; consented outputs are written under
`data/sessions/`. Both locations are excluded from Git. Artifacts and metrics can be retrieved
through either the CLI or the loopback-only API.

## Local development

```bash
uv sync --all-groups
uv run playwright install chromium
uv run alembic upgrade head
uv run voice-interviewer doctor
uv run voice-interviewer serve
```

Run all checks with:

```bash
make check
```
