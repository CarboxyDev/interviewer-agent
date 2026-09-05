# V2-004 live baseline preflight

Date: 2026-09-05. Outcome: blocked before campaign collection. This is a local readiness report,
not a conversation, latency, reliability, or cost result. No provider probe, paid synthesis,
meeting join, microphone capture, or benchmark interview was started.

## Observations

- The Docker daemon was initially unavailable. Launching the installed Docker application by its
  full path restored it. The existing, stopped Compose service was started for readiness checks.
- Native macOS doctor failed browser, PulseAudio tools, and audio devices. Inside the existing Linux
  container, `voice-interviewer doctor` passed all seven local readiness checks. `/health/ready`
  returned `status: ok`. These checks do not establish signed-in Meet access or provider access.
- The inspected container used `gpt-transcribe`, `gpt-5.6-luna`, `gpt-4o-mini-tts`, voice `cedar`,
  reasoning `none`, STT delay `low`, and 500 ms ending silence, matching those protocol fields.
- The active configuration had both Meet retry limits set to zero. The protocol requires a
  300-second same-link cooldown and three attempts per profile per hour. Existing settings were
  left untouched; they cannot be used as the fixed benchmark configuration.
- SHA-256 comparison of all 19 Python modules found four container/source differences:
  `domain.py`, `meet.py`, `ports.py`, and `runner.py`. A healthy old image is not the pinned V1
  baseline. The image was not rebuilt or relabelled as verified baseline evidence.
- No isolated synthetic candidate audio route, campaign meeting authorization, provider usage
  attribution, or enforced campaign spend cap was established during preflight.

## What remains before collection

1. Build a dedicated benchmark image from the pinned source and verify all runtime hashes plus the
   lockfile. Do not substitute the currently installed image for that build.
2. Use isolated benchmark storage and an explicit configuration matching `run-template.json`,
   including the existing admission safeguards. Preserve the ordinary demo's settings and data.
3. Establish the authorized test meeting and candidate-side fixture playback route. Verify account
   access, input/output isolation, explicit consent, and deletion before scored attempts.
4. Establish the spend cap and usage attribution, then perform the unscored warm-up and 20 measured
   attempts under the protocol. Provider/model availability is still unverified.

Measured attempts: none. Latency, conversation quality, reliability, and provider cost: unavailable.
The preflight did not create a scored campaign; no zero-valued performance results are reported.
V2-004 remains unchecked. Independent M0 architecture decisions can proceed while it is blocked.
