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

## Cascade hardening

Only completed STT utterances enter the LLM context. Resume and role text produce a bounded STT
prompt and a capped keyword list, improving recognition of names and technical terms without
changing the cascade. Completed Realtime items are correlated by `item_id` and duplicates are
discarded. One cursor owns the persistent Realtime event iterator for the whole interview. A
pending read is carried into the next conversation turn instead of starting an overlapping read.

The live transcription model does not provide a dependable confidence score, so the service does
not invent one. It uses conservative deterministic checks for empty, inaudible, or obviously
repeated output and asks the candidate to repeat once by default. The LLM policy also treats every
document and transcript as untrusted data and must clarify uncertainty rather than guessing.

TTS playback and candidate response waiting have separate deadlines. The candidate response timer
starts after playback completes, or immediately when a speech-start event interrupts playback.
This preserves the full answer window even for a longer question. Adjacent completed STT segments
are combined across a short configurable pause so a multi-sentence answer is not truncated.

STT, LLM, TTS, reasoning effort, VAD, supported transcription controls, context limits,
clarification attempts, and timeouts are configured through environment settings. Setting
reasoning effort to `none`, STT context limits to `0`, or clarification attempts to `0` disables
those optional behaviors.

## State machine

```text
CREATED -> PREPARING -> JOINING -----------------------> WAITING_FOR_PARTICIPANT
                            |                                      |
                            -> AWAITING_ADMISSION ------------------>
                                   |
                            manual host approval

WAITING_FOR_PARTICIPANT -> AWAITING_CONSENT -> ACTIVE -> FINALIZING -> COMPLETED

Any nonterminal state -> STOPPED or FAILED
```

State changes are append-only events. A process restart marks interrupted sessions as failed rather
than pretending that an interview is still active.

## Meet boundary

The official Google Meet Media API is receive-only, so it cannot deliver interviewer audio. Version
1 uses a normal Chromium participant, either anonymous or backed by a dedicated profile that the
operator signed into manually. An explicitly invited account can use `Join now` directly. If Meet
requires admission, the adapter clicks `Ask to join` once and waits for manual host approval within
a configured timeout. Denial, timeout, CAPTCHA, account recovery, or another security step fails
closed without another admission request or a security bypass attempt. A persistent retry limiter
defaults to a five-minute same-link cooldown and three attempts per browser profile per hour. Both
limits are configurable, and `0` disables a limit for an explicitly authorized controlled demo.
