# Configuration

Copy `.env.example` to `.env` for local Docker runs. Never commit the populated `.env`, browser
profile, input documents, database, or generated interview artifacts.

## Provider models

| Setting | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | empty | Required for live OpenAI calls |
| `INTERVIEWER_STT_MODEL` | `gpt-transcribe` | Streaming transcription model |
| `INTERVIEWER_LLM_MODEL` | `gpt-5.6-luna` | Interview planning and question generation |
| `INTERVIEWER_TTS_MODEL` | `gpt-4o-mini-tts` | Streaming speech synthesis model |
| `INTERVIEWER_TTS_VOICE` | `cedar` | Synthesized interviewer voice |
| `INTERVIEWER_REASONING_EFFORT` | `none` | LLM reasoning effort and latency tradeoff |

The default STT model is used because the interview loop depends on server-side speech-start and
silence events. A transcription model without those events requires a separate turn detector and
is not a drop-in replacement.

## Transcription and turn detection

| Setting | Default | Purpose |
| --- | --- | --- |
| `INTERVIEWER_STT_LANGUAGE` | `en` | Expected spoken language |
| `INTERVIEWER_STT_DELAY` | `low` | Optional latency control for supported models |
| `INTERVIEWER_STT_VAD_THRESHOLD` | `0.5` | Speech-detection sensitivity |
| `INTERVIEWER_STT_PREFIX_PADDING_MS` | `300` | Audio retained before detected speech |
| `INTERVIEWER_STT_SILENCE_DURATION_MS` | `500` | Silence required to complete an utterance |
| `INTERVIEWER_STT_CONTEXT_MAX_CHARS` | `3000` | Maximum resume and role context sent to STT |
| `INTERVIEWER_STT_KEYWORD_LIMIT` | `40` | Maximum expected terms sent to STT |
| `INTERVIEWER_TRANSCRIPT_CLARIFICATION_ATTEMPTS` | `1` | Repeat requests after unusable transcription |

Set either STT context limit to `0` to disable that hint mechanism. Set clarification attempts to
`0` to disable the deterministic repeat request.

## Meet safety and interview timing

| Setting | Default | Purpose |
| --- | --- | --- |
| `INTERVIEWER_MEET_ATTEMPT_COOLDOWN_SECONDS` | `300` | Same-link retry cooldown |
| `INTERVIEWER_MEET_ATTEMPT_HOURLY_LIMIT` | `3` | Profile-wide admission-attempt limit |
| `INTERVIEWER_ADMISSION_TIMEOUT_SECONDS` | `120` | Maximum wait for manual host admission |
| `INTERVIEWER_PARTICIPANT_TIMEOUT_SECONDS` | `300` | Maximum wait for the candidate |
| `INTERVIEWER_CONSENT_TIMEOUT_SECONDS` | `120` | Maximum wait for explicit consent |
| `INTERVIEWER_RESPONSE_TIMEOUT_SECONDS` | `20` | Initial candidate-response window |
| `INTERVIEWER_CANDIDATE_TURN_TIMEOUT_SECONDS` | `120` | Maximum active answer duration |
| `INTERVIEWER_CANDIDATE_TURN_GRACE_SECONDS` | `1.0` | Pause allowed between answer segments |
| `INTERVIEWER_TTS_TIMEOUT_SECONDS` | `45` | Maximum bot playback time |

Keep the retry cooldown and hourly limit enabled. A value of `0` disables the corresponding
safeguard and must not be used to work around admission denial or Google security friction.

## Runtime and storage

| Setting | Default | Purpose |
| --- | --- | --- |
| `INTERVIEWER_ENVIRONMENT` | `development` | Runtime environment label |
| `INTERVIEWER_DATA_DIR` | `./data` | Session database, profiles, and artifact root |
| `INTERVIEWER_DATABASE_URL` | `sqlite+aiosqlite:///data/interviewer.db` | SQLAlchemy database URL |
| `INTERVIEWER_HOST` | `0.0.0.0` | Service bind address inside the container |
| `INTERVIEWER_PORT` | `8000` | Service port inside the container |
| `INTERVIEWER_API_PORT` | `8000` | Loopback host port published by Compose |
| `INTERVIEWER_LOG_LEVEL` | `INFO` | Application log level |
| `INTERVIEWER_HEADLESS` | `false` | Browser headless mode |
| `INTERVIEWER_BROWSER_PROFILE_DIR` | `./data/browser-profile` | Persistent dedicated browser profile |
| `INTERVIEWER_BROWSER_CONNECTION_MODE` | `cdp` | Playwright browser connection method |
| `INTERVIEWER_BROWSER_CDP_PORT` | `9222` | Loopback Chrome DevTools port |
| `INTERVIEWER_BROWSER_DESKTOP_PORT` | `6080` | Loopback noVNC desktop port |

Docker supplies the Chrome executable path. Direct local runs may instead set either
`INTERVIEWER_BROWSER_CHANNEL` or `INTERVIEWER_BROWSER_EXECUTABLE_PATH` to a browser installed on
the same machine.

## Latency metrics

Completed or consented partial sessions include raw timing events and count, average, p50, p95,
and maximum summaries. The primary measurements are:

- `stt.audio_segment`: server VAD audio window, padding, and end silence
- `stt.post_speech`: detected speech end to final transcript receipt
- `llm.request.next_turn`: transcript processing and next-question generation
- `tts.first_audio`: TTS request start to first PCM audio chunk
- `pipeline.response_to_first_audio`: final transcript to first bot audio
- `pipeline.response_to_playback_end`: final transcript to completed bot playback

Inspect them through the local API or CLI:

```bash
docker compose exec interviewer voice-interviewer interview metrics SESSION_ID
```
