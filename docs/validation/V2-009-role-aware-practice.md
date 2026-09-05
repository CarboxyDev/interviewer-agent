# V2-009: Role-neutral interviewer and role-driven practice

Validated locally on 2026-09-05. User priority: both the interviewer and the UI must support
professional roles beyond backend engineering, with candidate-friendly content.

## Runtime

- Planning already accepts arbitrary job descriptions and resumes. Each next-turn request includes
  the plan, recent conversation and remaining time. There is no backend-only role schema.
- Removed the hard-coded backend interview label from transcription hints. Vocabulary continues to
  come from the supplied role and resume.
- Planning policy explicitly derives competencies and seniority from the role. It explores software
  engineering only when supported by the supplied context. Source attribution and correction rules
  remain intact; job requirements must never become assumed candidate experience.
- Replaced engineering-only clarification, non-answer, ownership and topic-change fallbacks with
  neutral professional questions. The fallback is deliberately generic because it has no trusted
  structured role context. It does not invent a role-specific question after failed generation.
- Six fake-provider cases exercise finance, product and customer-success planning, context delivery,
  and recovery after two invalid turns. A separate transcription check verifies finance vocabulary.
- `make check`: 168 tests pass, 88.92% measured runtime coverage; Ruff, formatting and strict Mypy pass.
  Runtime commit: `9b03486`.

## Sample UI

| Role | Professional focus | Second goal | Review audio |
| --- | --- | --- | --- |
| Backend engineer | Technical depth | Clarity | Existing matching synthetic answer |
| Product manager | Prioritization | Clarity | Written example only |
| Customer success manager | Customer communication | Clarity | Written example only |
| Finance analyst | Financial analysis | Clarity | Written example only |

The catalog in `prototypes/practice/scenarios.js` drives previews, initial questions, focused/mock
follow-ups, observations, evidence, revised answers, comparison and text downloads. Goals change the
question and coaching lens. Unsupported goal options were removed from the sample rather than left
as ineffective controls. The personal-context simulation stays in QA mode.

The visible question advances with the follow-up; Repeat repeats the current question. The sample
allows one original answer and one retry, with review becoming the primary action after each answer.
Starting the next focused practice preserves the role and clears answers and consent. Changing a
role after the ready check also clears consent, sound confirmation and review-audio choices.

Written-only examples cannot enable review audio and have no invented timestamps. The sound-check
clip remains a common voice sample; it is never presented as finance, product or customer-success
answer evidence.

`make prototype-test`: 41 Chromium tests pass in 197.34 seconds. The suite includes all eight
role/goal combinations through follow-up, repeat, evidence, retry, comparison, download and next
practice; mismatched-audio and consent checks; and the existing recovery, privacy, responsive-width
and candidate-language checks. In-app visual inspection confirmed finance setup and review.

## Boundaries

- UI content is authored synthetic material, not live generation or evaluation. Each role has one
  original answer and retry with two question/coaching variants. Mode and duration remain sample
  settings; this does not validate a full timed mock interview.
- The sample UI is not connected to the interview service. Live browser voice and adaptive coaching
  remain M2/M4 work. No provider call, real recording, deployment or candidate study was performed.
- Prompt and fake-provider tests verify instructions, source wiring and fallback behavior. They do
  not establish live model quality for any role or guarantee arbitrary-role suitability.
- Runtime changes intentionally diverge from the pinned V1 baseline in two modules. The original
  archive, image and benchmark fixtures are unchanged. Current-checkout baseline preflight must
  reject this divergence; use the retained pinned artifacts or a separate pinned checkout.
- M0 remains open until V2-004 live collection and its exit criteria pass.
