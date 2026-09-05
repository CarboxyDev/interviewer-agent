# Version 2 Plan: Candidate Interview Practice Studio

Status: In progress, product contract approved  
Current milestone: M0, product contract and benchmark baseline  
Current task: V2-002, create public synthetic fixtures  
Last updated: 2026-09-05

## Public plan decision

This plan belongs in the public repository. It explains product intent, engineering tradeoffs,
quality standards, and measurable progress without exposing private candidate data or credentials.
Public planning improves the portfolio story and makes implementation decisions easier to review.

The plan is the source of truth for V2. GitHub issues may be created when a milestone starts, but
they must reference the task IDs here and must not replace this document.

## Product direction

Version 2 turns the submitted Google Meet interviewer into a browser-first candidate practice
product. A candidate should be able to configure a role-focused practice interview, speak naturally
with the interviewer, and receive useful coaching grounded in what they actually said.

### Product promise

Practice a realistic interview, understand where an answer was strong or incomplete, and leave
with specific evidence-based ways to improve.

### Primary user

A job candidate preparing for a technical or professional interview.

### Primary user journey

1. Choose a practice goal and either use a sample role or provide a resume and job description.
2. Select focused practice or a realistic mock interview, then choose the session duration.
3. Preview the interview focus, review data handling, and complete a microphone check.
4. Grant recording and transcription consent immediately before the session starts.
5. Complete a calm voice interview with clear listening, thinking, and speaking states.
6. Receive a short summary of what to improve first, supported by transcript evidence.
7. Replay an answer, retry it, and compare the new attempt with the original.
8. Continue with a suggested focused practice session, export the report, or delete the session.

## Practice experience and UX contract

The product must feel like a private practice room, not recruiting software and not an engineering
dashboard. The candidate's attention belongs on speaking and reflecting. System details should be
available when useful but must not compete with the practice task.

### Practice modes

#### Focused practice

- The candidate selects one goal such as behavioral stories, system design explanation, technical
  depth, clarity, or concise answers.
- The session covers a small number of questions and prioritizes repetition and improvement.
- Coaching appears after the practice segment, not while the candidate is answering.
- The candidate can retry an answer and compare attempts.

#### Mock interview

- The interview samples several role-relevant competencies within a chosen duration.
- The interviewer behaves realistically and does not coach between questions.
- The candidate receives feedback only after the interview ends.
- The final report identifies which competency should become the next focused practice session.

Sample mode and personal mode are content choices, not separate practice experiences. Sample mode
uses public synthetic content and should require no document upload. Personal mode uses the
candidate's resume or role description under the same consent, retention, and deletion rules.

### Screen flow

#### 1. Start

- Present one primary action: start a practice session.
- Let a first-time visitor use a sample scenario without creating an account.
- Explain the outcome in one sentence and show a secondary path for returning users or saved work
  only when that capability exists.

#### 2. Configure practice

- Ask for the practice goal before requesting documents.
- Provide useful defaults for mode and duration instead of exposing model or pipeline settings.
- Support a sample role, pasted role description, uploaded role document, and optional resume.
- Show a concise focus preview: expected format, approximate topics, and duration. Do not reveal a
  rigid question script.

#### 3. Ready check

- Explain what is recorded, why it is needed, how long it is kept, and how to delete it.
- Explain that transcription is required for adaptive interviewing and feedback, while retaining the
  audio recording is a separate candidate choice.
- Request microphone permission in context, then show a simple input-level check.
- Let the candidate hear a short interviewer voice sample and select from a small curated set if
  multiple voices are supported.
- Keep recording consent separate from browser microphone permission.
- Disable the start action until required checks pass, with a clear explanation and recovery path.

#### 4. Live interview

- Use one calm primary workspace with the interviewer state: listening, thinking, speaking, paused,
  reconnecting, or finishing.
- Keep the remaining time secondary and avoid progress pressure such as question counts or scores.
- Offer essential controls only: mute, repeat question, pause for a moment, end interview, and help.
- Keep captions optional and collapsible. Do not show a full scrolling transcript by default.
- Keep latency charts, model names, evaluation data, and debugging information out of this screen.
- Make transcription and optional recording state continuously visible after consent.
- Confirm the difference between ending the session and withdrawing consent with plain language.
- Recover from permission loss, network interruption, silence, or provider delay without trapping the
  candidate in an unexplained loading state.

#### 5. Preparing feedback

- Confirm that the interview is safely saved or deleted before showing a long-running state.
- Explain which outputs are being prepared and allow the candidate to leave the page safely.
- Preserve a clear recovery path if one report stage fails but transcript or audio is available.

#### 6. Practice review

- Lead with one prioritized improvement and one observed strength, not a wall of analytics.
- Organize feedback by question or competency using evidence from the candidate's own words.
- Link each observation to the transcript and the matching audio moment.
- Separate observed evidence from suggestions and model-generated example answers.
- Use qualitative coverage and confidence language. Do not display an employability score.
- Place detailed timing, pipeline, and system metrics in a secondary technical view.

#### 7. Retry and continue

- Let the candidate retry one answer without repeating the entire interview.
- Show the original and retry side by side with the evidence behind any changed feedback.
- Recommend one next action: retry again, practice the weak competency, or start another mock.
- Preserve candidate control to export or delete before encouraging another session.

### UX design direction

- Visual thesis: a calm, focused practice room with warm neutral surfaces, strong typography, one
  restrained accent, and voice activity as the main visual signal.
- Content plan: orient, configure, practice, reflect, and retry. Each screen has one dominant job.
- Interaction thesis: a clear transition into interview focus, responsive voice-state feedback, and
  direct evidence-to-playback navigation during review.
- Use minimal chrome and cardless layouts unless a card is itself an interaction.
- Avoid recruiter terminology, dense dashboard mosaics, decorative gradients, gamified scores, and
  ornamental motion.
- Motion should clarify state transitions and audio activity, remain restrained, and respect reduced
  motion preferences.
- Setup and review must work responsively. The primary interview experience should be optimized for
  a quiet desktop or laptop environment, with mobile-browser support documented honestly.

### UX acceptance criteria

- A first-time visitor can begin sample practice without an account or document upload.
- Before starting, the candidate understands the mode, goal, duration, recording behavior,
  retention, and deletion path.
- The candidate can always tell whether the interviewer is listening, thinking, speaking, paused,
  reconnecting, or finished.
- The primary live view contains no technical telemetry and has one visually dominant state.
- Captions are accessible but do not distract from realistic interview practice by default.
- Permission denial, device failure, silence, disconnection, and report failure each provide a clear
  recovery or exit path.
- Ending an interview preserves consented work; withdrawing consent clearly deletes recorded work.
- Every coaching observation opens its supporting transcript evidence and audio when the candidate
  chose to retain a recording.
- The candidate can retry an answer and understand what changed without receiving an employability
  or hiring score.
- Review ends with one clear next practice action rather than a generic list of recommendations.

## Version 1 baseline to preserve

V1 already provides:

- A modular async Python service with explicit ports and adapters.
- FastAPI and CLI control surfaces.
- A manually authenticated Playwright Google Meet transport.
- Isolated PulseAudio capture and playback with FFmpeg recording.
- A chained realtime STT, text LLM, and streaming TTS interview loop.
- Barge-in, multi-segment answers, clarification, repeat, pushback, and timeout handling.
- Explicit consent, withdrawal deletion, protected-topic guards, and no hiring verdict.
- SQLite state transitions and allowlisted filesystem artifacts.
- Transcript, audio, neutral notes, session metadata, and latency metrics.
- CI with linting, formatting, strict type checking, and 92 passing tests at the V2 baseline.

V2 must reuse these strengths. It must not become an unrelated rewrite.

## Product principles

- Candidate-first: optimize for useful practice, confidence, and control.
- Browser-first: Google Meet remains supported but is no longer the primary demo path.
- Evidence over verdicts: coaching claims link to transcript evidence and never become a hiring
  recommendation.
- Consent before capture: do not retain interview content before explicit consent.
- Data minimization: make audio retention optional and keep only what is needed for the selected
  practice experience.
- Evaluation-driven: measure conversation behavior, safety, latency, cost, and reliability.
- Transport-neutral: interview policy should not depend on Google Meet or one audio implementation.
- Honest observability: separate unit-test evidence from live provider and browser evidence.
- Public-safe by default: committed examples are synthetic and contain no personal data.

## V2 scope

### Included

- A polished responsive web application for interview setup, live practice, and review.
- Focused-practice and mock-interview modes with different coaching timing.
- A browser audio transport that does not require Google Meet or Docker on the candidate's device.
- The existing Google Meet mode retained as an advanced transport.
- A transport-neutral interview engine shared by browser and Meet modes.
- Structured interview plans based on the role and candidate-provided context.
- Optional captions, a secondary timer, clear conversation state, and essential session controls.
- Evidence-linked coaching with strengths, gaps, suggested answer improvements, and next steps.
- Answer retry and evidence-based comparison without repeating a full session.
- Automated conversation replay and evaluation scenarios.
- Comparative latency, quality, and cost measurements for viable voice pipeline options.
- Anonymous public demo mode with bounded cost and retention.
- Production diagnostics, structured telemetry, rate limits, and deletion controls.
- A public demo, architecture documentation, benchmark summary, and short demo video.

### Explicitly excluded from V2

- Candidate ranking, employability scoring, or hiring recommendations.
- Emotion, personality, identity, age, gender, or protected-characteristic inference.
- Automated Google sign-in, CAPTCHA handling, or admission-control bypasses.
- Recruiter ATS workflows, applicant tracking, or bulk candidate comparison.
- Calendar and email automation.
- Multi-tenant enterprise administration and billing.
- Native mobile applications.
- Coding sandboxes, screen analysis, or video analysis.
- Microservice or Kubernetes migration without measured need.

## Release success measures

All required measures must be generated from synthetic or explicitly approved test sessions.

| Area | V2 release target |
| --- | --- |
| Demo access | A visitor can start a sample or live browser practice session without Google Meet |
| Setup | Sample scenario reaches device check in under 60 seconds |
| Orientation | Before starting, the candidate understands the goal, mode, duration, recording, retention, and deletion behavior |
| Live focus | The primary interview screen shows state and essential controls without technical telemetry |
| Voice latency | Response-to-first-audio p50 at or below 2.5 seconds and p95 at or below 4 seconds |
| Interruption | Bot playback stops within 500 ms of the speech-start event |
| Conversation quality | At least 95% pass rate across the required behavioral evaluation suite |
| Safety | 100% pass rate for consent, protected-topic, source-grounding, and deletion checks |
| Evidence | Every displayed coaching claim links to transcript spans and, when retained, audio |
| Practice loop | A candidate can retry an answer, compare attempts, and start the recommended next practice |
| Recovery | Permission, device, network, silence, and report failures have actionable recovery paths |
| Reliability | At least 19 of 20 automated release smoke sessions finish or fail with an expected code |
| Privacy | Public sessions support immediate deletion and automated retention expiry |
| Quality gates | Lint, formatting, strict typing, unit tests, integration tests, and web tests pass in CI |
| Portfolio | Public app, demo video, architecture, benchmark, and sample report are linked in README |

The latency targets are release goals, not current claims. The baseline must be measured again on a
fixed evaluation setup before optimization begins.

## Target architecture

```text
Candidate browser
  |-- setup, device check, live transcript, review
  |-- browser audio transport
  v
FastAPI application
  |-- session API and realtime event channel
  |-- consent and retention policy
  v
Transport-neutral InterviewEngine
  |-- interview plan and turn policy
  |-- transcript and evidence model
  |-- deterministic safety guards
  |-- metrics and evaluation hooks
  |
  |-- BrowserTransport
  |-- GoogleMeetTransport
  |
  |-- ChainedVoicePipeline: STT -> LLM -> TTS
  `-- Optional RealtimeVoicePipeline after benchmark approval

Session repository + artifact storage + telemetry
```

The chained pipeline remains the trusted baseline. A speech-to-speech implementation may be added
behind the voice pipeline boundary only after a benchmark compares latency, conversational quality,
transcript reliability, policy control, cost, and interruption behavior.

## Milestone plan and checklist

### M0: Product contract and baseline

Goal: agree on the V2 outcome and create a reproducible baseline before restructuring code.

- [x] V2-001 Confirm this product contract, scope, non-goals, and release measures.
- [ ] V2-002 Create synthetic resume, role, transcript, and audio fixtures safe for the public repo.
- [ ] V2-003 Define the benchmark environment, dataset version, metric definitions, and run format.
- [ ] V2-004 Run and record the V1 conversation, latency, reliability, and cost baseline.
- [ ] V2-005 Document the current module dependency map and identify Meet-specific engine coupling.
- [ ] V2-006 Decide the web stack and record the choice in the Decision log.
- [ ] V2-007 Decide the first public hosting shape and record data-flow and cost boundaries.
- [ ] V2-008 Validate the practice modes and screen flow with a low-fidelity interactive prototype.

Exit criteria:

- The product contract is approved.
- Baseline results can be reproduced without private data.
- Architecture and hosting decisions needed for M1 are recorded.
- The prototype validates the default journey, practice modes, and recovery paths before M2.

### M1: Evaluation foundation and engine boundary

Goal: make interview behavior replayable and separate the interview engine from Google Meet.

- [ ] V2-101 Define a versioned conversation scenario schema.
- [ ] V2-102 Build a transcript and speech-event replay runner.
- [ ] V2-103 Add required scenarios for consent, silence, unclear speech, repetition, thinking,
  clarification, pushback, interruption, candidate departure, and graceful ending.
- [ ] V2-104 Add source-grounding and prompt-injection scenarios for resume, role, and transcript data.
- [ ] V2-105 Add deterministic graders for state, safety, question shape, duplication, and artifacts.
- [ ] V2-106 Add rubric-based graders for relevance, adaptation, evidence, and coaching usefulness.
- [ ] V2-107 Calibrate rubric graders against a small human-reviewed reference set.
- [ ] V2-108 Extract a transport-neutral `InterviewEngine` without regressing Meet behavior.
- [ ] V2-109 Add a voice pipeline boundary suitable for controlled implementation comparison.
- [ ] V2-110 Run evaluation and Meet regression suites in CI with separate reported results.

Exit criteria:

- Synthetic scenarios replay locally and in CI.
- Evaluation results show failure cases by scenario and criterion.
- Existing Meet orchestration still passes its focused and full checks.
- Engine code has no direct Playwright or PulseAudio dependency.

### M2: Browser practice experience

Goal: deliver the first complete browser-based candidate practice flow.

- [ ] V2-201 Scaffold the typed web application and shared API contract generation.
- [ ] V2-202 Build practice goal, mode, duration, role, and optional resume configuration.
- [ ] V2-203 Build transcription consent, optional audio retention, microphone permission, and the
  device-check experience.
- [ ] V2-204 Implement browser audio transport and realtime session events.
- [ ] V2-205 Build the distraction-free live screen with state, optional captions, and audio activity.
- [ ] V2-206 Add repeat, pause-to-think, graceful end, explicit recording withdrawal, and reconnect UX.
- [ ] V2-207 Add accessible keyboard, focus, reduced-motion, and responsive behavior.
- [ ] V2-208 Add component, API-contract, and browser end-to-end tests.
- [ ] V2-209 Preserve a working advanced Google Meet launch path.
- [ ] V2-210 Add actionable permission, device, silence, network, provider, and report failure states.

Exit criteria:

- A candidate completes a synthetic browser interview from setup through review-ready artifacts.
- Consent and deletion behavior is verified through browser tests.
- The flow works on current desktop Chrome and Safari, with Firefox behavior documented.
- Meet mode remains operational or has an explicitly documented external blocker.
- The live screen satisfies the UX contract and keeps technical telemetry secondary.

### M3: Voice quality and latency

Goal: make the interview feel responsive and select the voice architecture with evidence.

- [ ] V2-301 Instrument browser, network, STT, reasoning, TTS, playback, and interruption timing.
- [ ] V2-302 Benchmark the existing chained pipeline on the fixed V2 dataset.
- [ ] V2-303 Test prompt, context, model, streaming, and prefetch optimizations independently.
- [ ] V2-304 Prototype a speech-to-speech pipeline behind the shared boundary.
- [ ] V2-305 Compare both pipelines on latency, quality, transcript fidelity, safety, cost, and recovery.
- [ ] V2-306 Record an architecture decision selecting the production default and fallback.
- [ ] V2-307 Meet the release latency and interruption targets without lowering safety pass rates.
- [ ] V2-308 Publish a reproducible benchmark summary with limitations.

Exit criteria:

- The selected pipeline meets the release targets on the fixed dataset.
- The architecture decision includes measured tradeoffs and a rollback path.
- Evaluation results show no safety or source-grounding regression.

### M4: Evidence-linked coaching report

Goal: turn raw artifacts into an actionable candidate improvement experience.

- [ ] V2-401 Define structured competencies, evidence spans, coaching observations, and uncertainty.
- [ ] V2-402 Generate evidence-linked strengths and improvement opportunities.
- [ ] V2-403 Add answer-level playback and transcript navigation from each observation.
- [ ] V2-404 Add suggested answer structure and a clearly labelled example improvement.
- [ ] V2-405 Add competency coverage without employability or hiring scores.
- [ ] V2-406 Add a next-practice plan based on uncovered or weakly evidenced areas.
- [ ] V2-407 Add export for a candidate-owned report with deletion controls.
- [ ] V2-408 Evaluate factual grounding, evidence completeness, and coaching usefulness.
- [ ] V2-409 Add answer retry with original-to-retry evidence comparison.
- [ ] V2-410 Turn the highest-priority improvement into a focused next practice session.

Exit criteria:

- Every displayed observation links to transcript evidence.
- Unsupported claims are rejected or explicitly labelled uncertain.
- A candidate can move from feedback to the relevant transcript and audio moment.
- The report contains no hiring recommendation or protected-trait inference.
- A candidate can retry an answer and continue into one recommended next practice action.

### M5: Production and portfolio release

Goal: ship a safe public experience and make its engineering quality immediately understandable.

- [ ] V2-501 Add anonymous session rate limits, quotas, abuse controls, and bounded provider spend.
- [ ] V2-502 Add automated retention expiry, immediate deletion, and orphan cleanup.
- [ ] V2-503 Add production-safe error handling, correlation IDs, health checks, and telemetry.
- [ ] V2-504 Add deployment smoke tests and rollback documentation.
- [ ] V2-505 Deploy the public sample and live browser practice experience.
- [ ] V2-506 Publish a synthetic sample session and evidence-linked report.
- [ ] V2-507 Update README with screenshots, demo link, demo video, benchmark, and architecture story.
- [ ] V2-508 Decide and document the repository license. Public source is not automatically open source.
- [ ] V2-509 Run a privacy, accessibility, cost, and release-readiness review.
- [ ] V2-510 Tag the V2 release and archive the final release evidence.

Exit criteria:

- A new visitor can understand and try the product from README.
- Public usage has bounded cost, retention, and deletion behavior.
- Deployment and release smoke checks pass.
- Published claims are supported by retained synthetic release evidence.

## Required evaluation scenarios

The release suite must include typical, edge, and adversarial cases:

- Clear substantive, partial, vague, incorrect, and non-answer responses.
- Silence, noisy or unusable transcript, long pauses, and multi-segment answers.
- Candidate interruption during consent, opening, normal question, and closing speech.
- Repeat requests, clarification requests, scope questions, and correction of interviewer premises.
- Pushback after already answering and explicit boundaries around work the candidate did not own.
- Early graceful end, participant departure, recording withdrawal, and deletion request.
- Resume and role contradictions, unsupported assumptions, and hallucinated experience.
- Prompt injection in the resume, job description, and spoken transcript.
- Protected-topic requests and attempts to obtain hiring or employability judgments.
- Provider timeout, disconnect, duplicate events, reconnect, and artifact-finalization failure.

## Risk register

| Risk | Impact | Planned response |
| --- | --- | --- |
| Browser voice latency remains high | Core experience feels unnatural | Benchmark both pipeline shapes before selecting the production default |
| Model changes improve speed but reduce control | Safety or evidence regression | Use must-pass eval gates and keep the chained fallback |
| Meet DOM changes break the advanced transport | Demo or regression failure | Keep Meet smoke tests separate and make browser mode the public path |
| Public demo creates unbounded cost | Unexpected provider spend | Quotas, short sessions, sample replay, rate limits, and a kill switch |
| Candidate documents expose personal data | Privacy and portfolio risk | No public retention by default, explicit consent, TTL, deletion, and synthetic fixtures |
| Coaching becomes hiring judgment | Ethical and product-scope drift | Candidate-facing language, evidence links, and prohibited-output evals |
| UI work hides weak interview quality | Attractive but unreliable demo | Evaluation foundation precedes browser feature completion |
| Scope expands into a full recruiting platform | Release delay | Keep recruiter, ATS, calendar, billing, and multi-tenant work out of V2 |

## Decision log

| Date | Decision | Status | Rationale |
| --- | --- | --- | --- |
| 2026-09-05 | V2 is primarily a candidate interview practice product | Accepted | Publicly demoable, useful to an individual candidate, and avoids automated hiring scope |
| 2026-09-05 | Keep the V2 plan in the public repository | Accepted | The plan improves transparency and contains no private operational information |
| 2026-09-05 | Browser mode becomes primary and Meet becomes advanced | Accepted | Removes the largest barrier to trying the project while preserving the existing integration |
| 2026-09-05 | Preserve chained voice as baseline and benchmark speech-to-speech | Accepted | Avoids a rewrite before latency, control, cost, and quality are compared |
| 2026-09-05 | Use evidence-linked coaching without employability scoring | Accepted | Provides candidate value while preserving the project's safety boundary |
| 2026-09-05 | Keep the live interview distraction-free and move technical detail to review | Accepted | Realistic practice requires attention on the conversation rather than a dashboard |
| 2026-09-05 | Support focused practice and mock interview modes | Accepted | Candidates need both realistic rehearsal and a short improvement loop |

## Current status

- V1 repository checks pass with 92 tests and 88.92% measured coverage.
- V1 has successful live Google Meet rehearsal evidence and retained local artifacts.
- Historical metrics show a material response-latency gap, but M0 must establish a fixed V2 baseline.
- V2-001 is approved by the instruction to start implementing this plan autonomously.
- Current work: V2-002 synthetic fixtures, followed by V2-003 benchmark protocol.
- M0 remains open; no new live baseline or V2 product behavior is claimed.

## Evidence log

Add one row when a task is completed. Do not add private artifact paths or meeting identifiers.

| Date | Task | Evidence | Remaining limitation |
| --- | --- | --- | --- |
| 2026-09-05 | V2-001 | User authorized implementation of the current plan; scope, non-goals, UX contract, milestone order, and release targets accepted | Release targets remain unmeasured goals |
| 2026-09-05 | Planning baseline | `docs/v2-plan.md` and repository instructions created | Superseded by V2-001 approval below |

## Plan change log

| Date | Change |
| --- | --- |
| 2026-09-05 | Created the V2 candidate practice product plan and checklist |
| 2026-09-05 | Simplified plan metadata and added the candidate practice UX contract |
