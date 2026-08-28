# Architecture

## Shape

The service is an async modular monolith. Domain code depends on ports, and external systems are
adapters. This keeps the interview logic testable without Google Meet, audio devices, or paid API
calls.

```text
FastAPI / Typer
      |
InterviewService -> InterviewRunner -> ConversationEngine
      |                    |                  |
SessionRepository     MeetTransport      STT -> LLM -> TTS
ArtifactStore         AudioRouter
```

## Core ports

- `MeetTransport`: joins, observes participant state, and leaves safely
- `AudioRouter`: exposes isolated candidate input and bot output streams
- `SpeechToText`: streams candidate utterance events
- `Interviewer`: plans the next question from structured context
- `TextToSpeech`: streams bot PCM audio
- `SessionRepository`: persists metadata and state transitions
- `ArtifactStore`: owns interview files and deletion

## Audio topology

```text
Chromium output -> PulseAudio meet_output sink -> monitor -> STT and candidate stem
TTS PCM         -> PulseAudio bot_microphone sink -> monitor -> Chromium microphone
candidate stem + bot stem -> FFmpeg mix -> interview.mp3
```

The streams are isolated so the bot does not transcribe itself. The mixer begins only after
explicit consent.

## State machine

```text
CREATED -> PREPARING -> JOINING -> WAITING_FOR_PARTICIPANT
        -> AWAITING_CONSENT -> ACTIVE -> FINALIZING -> COMPLETED

Any nonterminal state -> STOPPED or FAILED
```

State changes are append-only events. A process restart marks interrupted sessions as failed rather
than pretending that an interview is still active.

## Meet boundary

The official Google Meet Media API is receive-only, so it cannot deliver interviewer audio. Version
1 uses a normal Chromium guest participant. It clicks only `Join now`. If the page requires `Ask to
join`, sign-in, CAPTCHA, or another security step, the adapter fails closed.

