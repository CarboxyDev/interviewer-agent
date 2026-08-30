# Product requirements

## Goal

Given an authorized Google Meet URL, a resume, and a job description, join as an AI interviewer,
initiate a natural interview, and save consented outputs locally.

## Version 1 scope

- One adult candidate and one bot
- English only
- One active interview per service instance
- 5 to 45 minutes, default 30
- Resume and job description in PDF, DOCX, or TXT
- Dedicated or guest Google Meet participant named `AI Interviewer`
- Direct invited-account admission with one-shot `Ask to join` fallback
- Explicit streaming cascade: STT, text LLM, TTS
- Interruption handling that stops bot speech when the candidate speaks
- Configurable model, reasoning, VAD, latency, timeout, and clarification controls
- Bounded resume and role terminology supplied to STT for domain-aware transcription
- Deterministic repeat request for clearly unusable transcription output
- Local SQLite metadata and filesystem artifacts
- FastAPI and CLI control surfaces
- Newest-first paginated session history and local-only artifact downloads
- Per-stage and end-to-end cascade latency metrics with summary percentiles

## Conversation behavior

1. Greet the candidate and disclose that this is an AI-run interview.
2. Ask for explicit recording and transcription consent.
3. If consent is declined or unclear, do not record and leave.
4. After consent, state the approximate configured duration, explain the interview format, and
   begin with a short background question.
5. Adapt follow-ups to the resume, job description, and prior answers.
6. For a substantive answer, briefly acknowledge one concrete detail before the next focused
   question. For an unclear response or non-answer, acknowledge the gap naturally and clarify,
   narrow, or change topic without inventing useful context.
7. Ask one concise, verbally answerable question with one answer target at a time.
8. Split broad design exercises into progressive questions about individual decisions.
9. Narrow once or change topics when the candidate says they do not know or finds a task difficult
   to answer verbally.
10. Never ask a substantially identical question twice unless the candidate explicitly requests a
    repeat. After one recovery attempt on a vague answer, accommodate it by changing angle or topic.
11. Treat a short request to think as a pause, not a completed answer, and keep waiting.
12. Repeat the current question deterministically when the candidate asks, without advancing the
    interview plan.
13. Treat the requested duration as a soft target. Finish the current answer before closing.
14. Always play a deterministic closing statement before stopping recording and leaving.
15. If the candidate leaves unexpectedly, stop cleanly and retain the consented partial artifacts.

## Outputs

- `interview.mp3`: mixed candidate and bot audio after consent
- `transcript.json`: ordered speaker-labelled utterances with timestamps
- `transcript.md`: readable transcript
- `notes.md`: factual themes and supporting evidence, without a hiring verdict
- `session.json`: state transitions, configuration, and failure details
- `metrics.json`: raw STT, LLM, TTS, playback, and end-to-end timing events with summaries

## Non-goals

- Google account sign-in automation
- Repeated admission requests or admission, CAPTCHA, and security-control bypasses
- Video analysis, emotion detection, or identity inference
- Candidate ranking, scoring, or hiring recommendation
- Calendar scheduling or a custom UI
- Concurrent interviews
- Coding environment or screen sharing

## Acceptance criteria

- The bot starts the conversation after the candidate is present.
- No interview content is persisted before explicit consent.
- Candidate speech interrupts bot playback within 500 ms of the speech-start event.
- The candidate response timeout starts only after bot playback ends or is interrupted.
- Duplicate completed STT events never become duplicate candidate utterances.
- Clearly inaudible transcription triggers one configurable repeat request.
- The post-consent opening explains the format before technical questioning begins.
- Each generated follow-up responds to the assessed answer quality. It grounds substantive
  acknowledgments in a concrete detail and never praises or advances from a non-answer.
- A near-duplicate generated question is repaired or replaced with a different angle.
- A generated multi-part or oversized spoken question is repaired once, then replaced by a safe
  focused fallback if still invalid.
- Candidate departure results in `STOPPED`, not `FAILED`, with available partial artifacts.
- Reaching the target duration never causes a new question or an abrupt exit. The current answer
  receives its configured response window, followed by the deterministic closing statement.
- Normal responses begin within 3 seconds on a healthy network.
- Each consented completed or partial interview exposes latency events and average, p50, p95, and
  maximum summaries through the artifact API.
- The agent never asks about protected personal characteristics.
- A second concurrent start returns HTTP 409.
- A manual admission request is sent at most once and has a configurable timeout.
- Admission denial, timeout, or Google security friction causes a stable, visible failure and no
  bypass attempt.
- Final artifacts are available within 15 seconds of leaving the meeting.
- Recent sessions are returned newest first with bounded pagination.
- Only generated output files can be downloaded; uploaded input documents are not API artifacts.
