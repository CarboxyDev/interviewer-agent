# V2-004 pinned baseline preparation

Date: 2026-09-05. Outcome: offline provenance verified; live collection remains blocked.
This extends the [earlier preflight](2026-09-05-v1-preflight.md), not a measured campaign.

## Completed preparation

- Added `python -m benchmarks.preflight` to verify the immutable V1 baseline, protocol hash,
  all nine synthetic fixture assets, and 28 local runtime/build inputs. The current working tree
  matches the baseline. The tool does not read `.env` or import provider configuration.
- Created an ignored preparation folder with 20 attempts explicitly marked `not_run`, null results
  and cost, outstanding blockers, and a hash-pinned Git build-context archive. No existing evidence
  is overwritten, and ordinary demo settings/storage are not modified.
- The old demo image fails the new provenance check on four runtime modules and `pyproject.toml`.
  This adds package-configuration drift to the four modules identified in the earlier report.
- Built `interviewer-v1-benchmark:dcfd7d4` from the pinned archive, using the baseline Dockerfile and
  frozen lockfile. The build verified the Dockerfile's pinned Chrome download checksum.
- Image ID: `sha256:bd4f416f50e22d119a30f3e653a6a09352622483fe9adb6f535d86077739f56c`.
  Python version: `3.12.14`. A read-only, network-disabled probe verified all installed baseline
  inputs, including the 19 runtime Python modules, lockfile, package configuration, migrations,
  and entrypoint. No differing files remain in the dedicated image.
- Lockfile SHA-256: `eb7ca14716db27b4504201010747cbb59f98481e857fa0b9ef11eef8db087b6d`.
- Validation: 25 focused preflight tests; `make check` passes with 128 tests, 88.92% runtime coverage,
  Ruff, formatting, and strict Mypy across the runtime plus prototype/benchmark Python tooling.

## Remaining limits

`collection_ready` remains false. We still need the authorized synthetic meeting, manually
authenticated participant, verified candidate audio isolation, effective campaign settings,
provider/model access, an enforced attributable budget, and a consent/deletion warm-up.
No interview, microphone capture, paid provider request, or scored attempt was made.

The build pulled public container/package dependencies. This does not establish provider access.
The image probe bypassed the service entrypoint; it does not establish Chrome/PulseAudio runtime
readiness or Meet compatibility. Reuse this immutable image ID for a future campaign: upstream base
images and apt packages are not fully pinned, so a later rebuild may produce a different environment.

Measured attempts: none. Latency, conversation quality, reliability, and provider cost: unavailable.
V2-004 remains unchecked, and M0 remains open.
