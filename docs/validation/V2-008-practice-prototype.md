# V2-008 practice-flow validation

Date: 2026-09-05. Artifact: [interactive prototype](../../prototypes/practice/README.md).
Method: contract walkthrough plus automated local Chromium interactions using only fictional data.
No candidate study, live interview, provider result, microphone capture, or deployment is claimed.

Validation result: 27 Chromium browser checks pass on macOS; `make check` passes with 103
runtime/fixture tests, 88.92% runtime coverage, Ruff, formatting, and strict Mypy. In-app visual
walkthrough inspected start, configuration, readiness, and the live workspace. A separate browser
CI job is configured; no remote CI result is claimed.

## Acceptance mapping

| Contract | Prototype evidence |
| --- | --- |
| Default sample path, no account or upload | Start → configuration → ready check; fictional default role and optional sample resume |
| Goals before documents, useful defaults | Goal first; focused mode and five minutes; preview updates for mode, goal, and duration |
| Personal context choices | Sample pasted text and role document paths are visible; real input is explicitly unavailable |
| Required transcription, optional audio | Independent consent and device gates; audio retention is unchecked by default |
| Data handling before start | Planned 24-hour expiry and immediate deletion copy; separate explanation of the tab-only simulation |
| Calm live workspace | Dominant conversation state, secondary static timer, essential controls, collapsed captions |
| Both practice modes | Focused segment supports retry; mock practice provides no feedback between sample answers |
| Voice state and controls | Speaking, listening, thinking, pause, reconnecting recovery, and finishing transitions; mute/repeat/help |
| End versus withdraw | Separate dialogs explain preserving consented work versus clearing the session |
| Evidence before suggestions | Both displayed observations open exact fictional transcript quotes; optional original audio |
| Retry and comparison | One answer retry; side-by-side authored texts and quoted changed opening; no hiring score |
| One next practice action | Clarity practice focused on explaining the expiry tradeoff; export and deletion remain accessible |
| Failure recovery | Permission, device, silence, network, provider, and report scenarios each have recovery and exit controls |
| Keyboard and responsive foundation | Focus on screen entry/evidence, retained control focus, native dialogs, reduced motion, mobile width |

## Issues found and resolved

- Ending from recovery originally discarded the recovery key before rendering. Recovery exits now
  restore a paused live view before confirming the end, preserving the available sample answer.
- Abandoning a retry could hide the original feedback. Original-answer availability is tracked
  separately, so an empty retry preserves original evidence without inventing a comparison.
- Re-rendered live controls could lose keyboard focus. Controls and caption summaries now retain
  focus through state updates; dialogs return focus and leave the interview paused on cancellation.
- A general repository-root preview could expose unrelated files. The preview server now uses an
  explicit public asset allowlist and disables microphone/camera permission through response headers.

## Product work still required

M2 must implement real permission/device checks, reconnect semantics, generated API contracts,
server-enforced consent, accessible live announcements, uploads, and browser history behavior.
M4 must replace authored coaching with grounded model output, exact evidence timing, and recorded
retry comparison. M5 must prove durable save, ownership, retention, deletion, and safe background
report completion. No checklist credit for those later tasks is implied by this prototype.

M0 still depends on the V2-004 live baseline. Completing this interaction study does not authorize
skipping the baseline or starting the transport-neutral engine refactor.
