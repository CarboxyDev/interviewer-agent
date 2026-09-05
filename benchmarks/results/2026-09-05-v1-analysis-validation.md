# V2-004 raw-latency analysis validation

Date: 2026-09-05. Outcome: offline analysis behavior validated; no live measurement collected.

`python -m benchmarks.analyze_latency` now provides conservative raw-event aggregation for the
fixed baseline campaign. It keeps the stage, phase, and operation separate; pools raw samples;
uses nearest-rank quantiles; and rejects mixed settings/models, duplicate artifacts, invalid event
sequences, and invalid numeric input.

Playback failures, interruptions, and unmatched first chunks exclude onset samples for the affected
attempt/phase because V1 has no uniform turn correlation ID. Failed/incomplete attempts remain in
accounting. Withdrawal artifacts are rejected rather than retained. Raw reviews, item IDs, paths,
and unknown fields are not emitted.

Validation evidence:

- 33 focused tests cover empty inputs, pooled distributions, small samples, nearest-rank p95,
  partial playback, failed attempts, missing artifacts, withdrawal, configuration mixing, numeric
  validation, duplicate input, redaction, the CLI, and actual V1 `LatencyTracker` compatibility.
- Final `make check` passes: 161 tests, 88.92% runtime coverage, Ruff, formatting, and strict
  Mypy across the runtime and benchmark/prototype Python tooling. The separate prototype suite
  previously passed all 27 Chromium checks; no browser code changed in this analysis chunk.
- Running the CLI against the local preparation folder with an empty metrics directory reports
  all 20 attempts `not_run`, zero samples, and null latency, provider cost, audible onset, and
  interruption-stop timing. The campaign remains unmodified.
- Missing metric files are counted; missing stage samples remain null because V1 does not record
  a complete expected-event denominator. No synthetic zero replaces an unknown value.

This output is not a reliability score, cost report, human conversation review, source-provenance
check, or campaign-completion certificate. Those remain separate requirements under the protocol.
The 33 tests use authored data or a fake-clock tracker and establish no provider performance claim.
V2-004 and M0 remain open pending the authorized, isolated, budgeted live campaign.
