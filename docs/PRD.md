# Product requirements

## Goal

Given an authorized Google Meet URL, a resume, and a job description, join as an AI interviewer,
initiate a natural interview, and save consented outputs locally.

## Version 1 scope

- One adult candidate and one bot
- English only
- One active interview per service instance
- 5 to 45 minutes, default 15
- Resume and job description in PDF, DOCX, or TXT
- Guest Google Meet participant named `AI Interviewer`
- Explicit streaming cascade: STT, text LLM, TTS
- Interruption handling that stops bot speech when the candidate speaks
- Local SQLite metadata and filesystem artifacts
- FastAPI and CLI control surfaces

## Conversation behavior

1. Greet the candidate and disclose that this is an AI-run interview.
2. Ask for explicit recording and transcription consent.
3. If consent is declined or unclear, do not record and leave.
4. Begin with a short background question.
5. Adapt follow-ups to the resume, job description, and prior answers.
6. Ask one concise question at a time.
7. Cover relevant experience, technical depth, tradeoffs, and scenarios.
8. Reserve time for the candidate to add context and close politely.

## Outputs

- `interview.mp3`: mixed candidate and bot audio after consent
- `transcript.json`: ordered speaker-labelled utterances with timestamps
- `transcript.md`: readable transcript
- `notes.md`: factual themes and supporting evidence, without a hiring verdict
- `session.json`: state transitions, configuration, and failure details

## Non-goals

- Google account sign-in automation
- Admission, CAPTCHA, or security-control bypasses
- Video analysis, emotion detection, or identity inference
- Candidate ranking, scoring, or hiring recommendation
- Calendar scheduling or a custom UI
- Concurrent interviews
- Coding environment or screen sharing

## Acceptance criteria

- The bot starts the conversation after the candidate is present.
- No interview content is persisted before explicit consent.
- Candidate speech interrupts bot playback within 500 ms of the speech-start event.
- Normal responses begin within 3 seconds on a healthy network.
- The agent never asks about protected personal characteristics.
- A second concurrent start returns HTTP 409.
- Admission or Google security friction causes a stable, visible failure and no bypass attempt.
- Final artifacts are available within 15 seconds of leaving the meeting.

