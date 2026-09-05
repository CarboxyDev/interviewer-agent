# V1 benchmark protocol

V2-003. Protocol: `v1-baseline-1`. Status: defined, live campaign not yet run.

Purpose: record the existing chained pipeline before V2 engine changes. This protocol defines an
initial narrow baseline; it does not replace the M1 evaluation suite or establish V2 release gates.
The runtime baseline is commit `dcfd7d45504a33c838464ab152ec6d10f23fc65a`. Later fixture and protocol
commits may be used if `src/`, runtime configuration, and `uv.lock` are unchanged from that baseline.

## Inputs and versioning

Use [candidate-practice-v1](fixtures/v1/README.md). Record its manifest SHA-256 and the application
commit in each campaign. Never mix dataset versions, configurations, or transports in a percentile.
The reference utterances are authored inputs, not generated transcripts or a replay scenario schema.
A change to clips, prompts, model choices, timing, or setup starts a separate campaign.

## Environment

Two evidence lanes must be reported separately:

| Lane | Fixed setup | What it establishes |
| --- | --- | --- |
| Offline | Python 3.12, `uv sync --frozen --all-groups`, existing fake adapters, pinned fixtures | Repository checks and deterministic behavior only |
| Live Meet | Existing Docker Compose service, Linux container on one fixed host, dedicated manually authenticated bot, isolated PulseAudio input/output, real configured STT/LLM/TTS | Observed provider and Meet behavior on that environment |

For live runs, record host OS/version, architecture, CPU model, Docker CPU/memory allocation,
Docker version, container image ID, Python, Chrome, FFmpeg and PulseAudio versions, `uv.lock` hash,
operator region, network type, and UTC start/end. Keep the same host, image, network, and allocation
throughout the campaign. Docker's base image and apt dependencies are not fully pinned: reuse the
built image ID rather than assuming a rebuild is identical. Do not record a hostname, IP, account,
meeting identifier, profile path, credential, or complete environment dump.

Use the configuration in [run-template.json](run-template.json), copied explicitly from the V1
source defaults. Record actual effective nonsecret values rather than assuming `.env` matches them.
The model strings are repository configuration, not a claim that they remain available. If access
fails, record the failure and start a new labelled configuration if a model is changed. Do not
silently substitute models or tune VAD between repetitions.

Session duration is five minutes, concurrency is one, and audio input is mono 24 kHz signed 16-bit
PCM at real-time speed. Candidate clips enter the candidate-side Meet microphone through an isolated
virtual audio source. Bot playback must never feed that source. Use a manually admitted synthetic
participant and no real conversation. Record the routing tool/version and verify isolation first.
No automated sign-in or admission bypass is part of the benchmark.

## Run procedure and fixed probe matrix

1. Validate inputs and run `make check`. Record that as offline evidence, not a live success.
2. Copy `run-template.json` into ignored `data/benchmarks/<campaign-id>/run.json`. Fill environment,
   hashes, effective settings, and a provider spend cap before starting. The template is not a runner.
3. Establish the authorized private test meeting and isolated candidate playback route. Verify
   provider readiness, model access, recording consent, and safe cleanup in one unscored warm-up.
   Record warm-up cost and failure separately; a failed preflight blocks the live campaign.
4. Run five rounds of the four probes below, in the listed order, for 20 measured attempts. Wait
   at least the configured same-link cooldown (300 seconds) and respect the hourly profile limit
   (three attempts). Count the warm-up toward these limits. Do not disable the V1 admission limiter.
5. Start each clip 1000 ms after the relevant bot utterance finishes. Send silence between clips.
   Record actual trigger times and any operator deviation. Use the committed WAV frames, not a
   human rereading, for the measured candidate input. Any other spoken input invalidates that
   attempt's timing comparison, but the attempt and its reason remain in the reliability denominator.
6. Wait for finalization. Stop and classify as unexpected timeout if no terminal state arrives
   within 420 seconds after consent. Capture permitted outputs and deletion observations. Never
   replace a failed attempt with a rerun; append any rerun under a new attempt ID.
7. Review results, compute aggregates from raw events, and produce a public-safe summary. Keep raw
   session exports local: V1 `session.json` contains the meeting URL. Withdrawal must still remove
   session content; retain only non-content outcome counters for that probe.

| Probe | Candidate input sequence | Expected observation |
| --- | --- | --- |
| `answer_then_end` | `consent.wav` after disclosure; `answer.wav` after opening; `end.wav` after the next bot utterance | One grounded follow-up and graceful closing; `COMPLETED` with permitted outputs |
| `repeat_then_answer_then_end` | Consent; `repeat.wav` after opening; `answer.wav` after the next bot utterance; `end.wav` after the next bot utterance | Grade whether repetition is honored, then graceful closing and `COMPLETED`. V1 deterministic repeat detection misses this wording; record live behavior separately |
| `silence_after_consent` | Consent; silence throughout the active interview | Observe the V1 gap: active silence raises `FAILED / INTERNAL_ERROR`, with no transcript/metrics finalization. Count as a known failure, not successful recovery |
| `withdraw_after_answer` | Consent; answer after opening; `withdrawal.wav` after the next bot utterance | `STOPPED` and session content deleted, including inputs and any recording |

If the model ends before a scheduled answer or control clip can be delivered, record an incomplete
probe, not a pass. These probes intentionally reuse a small input set and include a silence-only
probe. They measure repeatability and recovery on that set, not realistic multi-turn interview
quality. V1 timeout paths do not finalize metrics, and withdrawal deletes content, so unavailable
samples must stay missing rather than being reconstructed. M1 supplies broader cases and a replay
runner. No benchmark orchestration or virtual microphone setup is
implemented by V2-003.

## Metrics and aggregation

Use monotonic time for durations and UTC only for run identity. The V1 definitions live in
`src/voice_interviewer/metrics.py`; measurement sites are in `runner.py`. Archive the raw metric
schema version with the run. For each metric and phase, publish count, missing count, failures,
interrupted count, p50, p95, and max. Quantiles use nearest rank: sorted value at
`ceil(percentile * count) - 1`. No interpolation. Empty samples produce `null`, never zero.
Pool eligible raw samples for one configuration, not per-session percentile values. Small samples
must be labelled; with fewer than 20 observations, p95 has particularly little resolution.

| Metric | Boundary and reporting rule |
| --- | --- |
| `pipeline.response_to_first_audio` | Final transcript receipt to first generated TTS PCM chunk. Separate `opening`, `interview`, `repeat`, `clarification`, and `closing` phases. Primary V1 comparison uses `interview` only. Excludes STT, output queueing, network playback, and the candidate device. |
| `stt.post_speech` | Server speech-stopped event receipt to final transcript receipt for one STT item. Does not include VAD endpoint delay or candidate-to-server transit. |
| `stt.audio_segment` | Server VAD offsets, including configured padding and ending silence. Segment length, not latency. |
| `llm.request` | Client-observed request duration, separated by `prepare`, `next_turn`, and `notes`. Includes any adapter-internal repair round trips. |
| `tts.first_audio` | Synthesis start to first generated PCM chunk. Not audible output. |
| `tts.playback` | Synthesis/routing start to completion or cancellation. Group failed and interrupted events separately from completed durations. |
| `pipeline.response_to_playback_end` | Final transcript receipt to completed server routing; not confirmed candidate-side playback completion. |
| Candidate-perceived response | Candidate speech end to first audible response at the candidate device. Unavailable in V1 telemetry; requires a correlated loopback measurement. Do not infer it by adding unpaired stage percentiles. |
| Interruption stop | Speech-start event receipt to cessation of bot output. Unavailable in V1 telemetry; M1/M3 need an event-linked measurement and interruption probe. |
| Reliability | Successful expected terminal state plus required artifacts or verified deletion, divided by all 20 scheduled measured attempts. Report completed, expected stopped, unexpected failures, incomplete probes, and not-run separately. Provider/admission failures and the known silence defect count as failures. Warm-up is separate. |
| Conversation observations | Human review of each delivered substantive-answer probe: source grounding, relevance to the answer, one focused question, no duplicated question except requested repetition, and no prohibited topic or hiring judgment. Report pass/fail/not-assessable per criterion with transcript evidence and reviewer method. When the model ends instead of asking a question, mark question-shape criteria not assessable. Not the M1 rubric-calibrated quality score. |
| Safety | Report current test results and observed consent/deletion checks separately. Missing instrumentation or scenarios are unverified. A V2 safety pass requires the full required suite, not this pack. |
| Cost | Actual usage by model/stage, including retries, preparation, consent, closing and notes. Apply a dated, sourced price table or isolated provider usage record; report provider cost and infrastructure cost separately. Missing usage or attribution is `null` with a reason, never free. |

V1 summaries group across phases and exclude events whose own status is not `completed`. A first
chunk can be recorded before later playback fails. Use raw events and flag such partial turns
rather than treating every first-chunk sample as a successfully completed response. V1 lacks a
uniform turn correlation ID; record ambiguous exclusions and do not claim fully paired timing.
The 2.5 s p50 / 4 s p95 release goal must specify its boundary before M3 compares it with browser
results. A fast server first-chunk result alone does not establish a responsive candidate experience.

## Run format and privacy

The [JSON template](run-template.json) is version 1 of the campaign record. `status` is `template`,
`blocked`, `partial`, or `completed`. `completed` means collection finished, not that acceptance
criteria passed. Required values that are unavailable remain `null` with an entry in `limitations`.
Do not report a completed campaign until environment, attempts, review, and metric availability
are accounted for. Public summaries contain synthetic aggregate evidence only.

Append one object per scheduled attempt to `attempts` with: `attempt_id`, `probe_id`, `round`,
`status` (`completed`, `failed`, `incomplete`, or `not_run`), `started_at_utc`, `ended_at_utc`,
`terminal_state`, `failure_code`, `expected_outcome_observed`, `deletion_verified`,
`artifact_kinds`, `metric_sample_counts`, `review` (criterion/outcome/evidence), and `deviations`.
Use an ordinal benchmark ID, not the application session ID. Withdrawal reviews contain no
retained transcript or content. Each aggregate in `results.latency` includes the stage, phase,
operation, count, missing count, exclusions, and quantiles in milliseconds. Each cost row includes
model, unit, measured quantity, unit price, price source/date, and calculated amount.

V1 has no benchmark spend enforcement or complete usage capture. Before paid runs, establish an
external provider cap or isolated monitored budget and record how it is enforced. Stop the campaign
if usage cannot be bounded or attributed; record remaining attempts as not run. Never expose keys
or account identifiers in benchmark reports. Paid provider latency and cost remain unmeasured
until V2-004 runs under those conditions.

## Current evidence

The initial offline V1 check passed on 2026-09-05: 92 tests, 88.92% coverage, Ruff, formatting,
and strict Mypy. The fixture suite adds 11 checks. These results do not measure provider latency,
Meet reliability, speech recognition accuracy, or cost. V2-004 remains open.

## V2-004 offline preparation tools

The preflight tool verifies the pinned protocol, all nine fixture assets, and 28 local runtime/build
inputs without importing provider settings or reading `.env`. Source drift produces filenames and
hash comparisons only, never source content or environment values.

```sh
uv run python -m benchmarks.preflight
uv run python -m benchmarks.preflight --prepare my-baseline-campaign
```

Preparation creates a new, ignored `data/benchmarks/my-baseline-campaign/` with:

- `run.json`: all 20 scheduled attempts explicitly `not_run`, warm-up unrun, cost and results unknown.
- `preflight.json`: provenance checks and outstanding live prerequisites.
- `build-context.tar` and `build-context.sha256`: allowlisted build inputs from the pinned baseline
  Git commit, not the working directory. No `.env`, candidate files, profiles, or credentials.

Campaign names are restricted and preparation refuses existing directories, symlinks, and runtime
drift. It never overwrites collected evidence. Use a fresh ID for a separate preparation.

Build a dedicated local image from that archive, preserving the ordinary Compose demo image:

```sh
docker build --tag interviewer-v1-benchmark:dcfd7d4 - < data/benchmarks/my-baseline-campaign/build-context.tar
uv run python -m benchmarks.preflight --image interviewer-v1-benchmark:dcfd7d4
```

The optional image probe resolves an immutable local image ID and runs only a file-hash/Python-version
probe with no networking, no mounts, a read-only root filesystem, and the normal entrypoint bypassed.
It does not launch Chrome, PulseAudio, the API, or an interview. It compares installed modules,
lockfile, package configuration, migrations, and the entrypoint with the pinned commit. Dockerfile
and ignore-file provenance comes from the archived build context, not files inside the image.

Exit code zero means the checks requested passed. **It never means the live campaign can start.**
`collection_ready` remains false: meeting authorization, candidate audio isolation, effective
campaign configuration, provider access, spend enforcement, and warm-up still need live verification.
Do not copy the ordinary demo `.env` or disable its admission safeguards to make a campaign run.
These tools neither enforce a provider budget nor establish usage attribution. Pulling build layers
is network activity, but image inspection itself has networking disabled and makes no provider calls.

Run `uv run pytest tests/test_benchmark_preflight.py --no-cov` for focused behavior checks. They use
fictional temporary inputs and fake subprocess outputs; actual local image evidence is reported
separately under `results/`. Runtime code and `uv.lock` remain unchanged.
