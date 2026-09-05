"""V2-004 offline provenance checks and unscored campaign preparation.

Never imports the runtime Settings, reads .env, joins Meet, or calls a provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "dcfd7d45504a33c838464ab152ec6d10f23fc65a"
TEMPLATE_HASH = "a57d85dabccc97187818c6e0a31d1fe7d89cecacaa67a08cc19d10c6099dd2b8"
MANIFEST_HASH = "8c4b3ef48cb69c5cbc8387a5ef22184b54b56f6c0a991be445bde91da3925edd"
BUILD_PATHS = (
    "Dockerfile",
    ".dockerignore",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "src",
    "migrations",
    "alembic.ini",
    "docker",
)
# README is copied for packaging, but documentation-only edits do not change runtime provenance.
RUNTIME_PATHS = tuple(path for path in BUILD_PATHS if path != "README.md")
LIVE_BLOCKERS = [
    "Authorized synthetic test meeting and manually authenticated participant are unverified.",
    "Isolated candidate-side audio playback and consent/deletion warm-up are unverified.",
    "Enforced provider spend cap and attributable usage are unverified.",
    "Live model access, effective campaign settings, and environment are unverified.",
]
PROBES = (
    "answer_then_end",
    "repeat_then_answer_then_end",
    "silence_after_consent",
    "withdraw_after_answer",
)
# This probe reads only public build inputs and prints no environment, profile, or candidate data.
IMAGE_PROBE = """
import hashlib, json, pathlib, platform
root = pathlib.Path('/app')
paths = sorted(root.joinpath('src').rglob('*'))
paths += [root / 'uv.lock', root / 'pyproject.toml', root / 'alembic.ini']
paths += sorted(root.joinpath('migrations').rglob('*'))
files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in paths if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
entrypoint = pathlib.Path('/usr/local/bin/interviewer-entrypoint')
files['docker/entrypoint.sh'] = hashlib.sha256(entrypoint.read_bytes()).hexdigest()
print(json.dumps({'files': files, 'python_version': platform.python_version()}))
"""


class PreflightError(ValueError):
    """A public-safe diagnostic; raw subprocess output is intentionally not echoed."""


def command(args: list[str], root: Path) -> bytes:
    try:
        return subprocess.run(  # noqa: S603
            args,
            cwd=root,
            check=True,
            capture_output=True,
            timeout=120,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise PreflightError(
            f"{args[0]} operation failed; inspect the local tool separately."
        ) from error


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def baseline_files(root: Path) -> dict[str, str]:
    raw = command(["git", "ls-tree", "-rz", "--name-only", BASELINE, "--", *RUNTIME_PATHS], root)
    paths = [path.decode() for path in raw.split(b"\0") if path]
    if not paths:
        raise PreflightError("Pinned baseline is unavailable in this checkout.")
    return {path: digest(command(["git", "show", f"{BASELINE}:{path}"], root)) for path in paths}


def local_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in RUNTIME_PATHS:
        base = root / name
        if base.is_symlink():
            raise PreflightError("Runtime input contains a symbolic link.")
        paths = base.rglob("*") if base.is_dir() else [base]
        for path in paths:
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.is_symlink():
                raise PreflightError("Runtime input contains a symbolic link.")
            if path.is_file():
                files[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return files


def differences(expected: dict[str, str], actual: dict[str, str]) -> list[str]:
    return sorted(
        path for path in expected.keys() | actual.keys() if expected.get(path) != actual.get(path)
    )


def load_template(root: Path) -> dict[str, Any]:
    content = (root / "benchmarks/run-template.json").read_bytes()
    if digest(content) != TEMPLATE_HASH:
        raise PreflightError("Run template differs from the pinned protocol.")
    template: dict[str, Any] = json.loads(content)
    return template


def check_dataset(root: Path) -> int:
    folder = root / "benchmarks/fixtures/v1"
    manifest_bytes = (folder / "manifest.json").read_bytes()
    if digest(manifest_bytes) != MANIFEST_HASH:
        raise PreflightError("Dataset manifest differs from the pinned version.")
    manifest = json.loads(manifest_bytes)
    for asset in manifest["assets"]:
        path = folder / asset["path"]
        if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
            raise PreflightError("Dataset asset escapes its fixture folder.")
        content = path.read_bytes()
        if digest(content) != asset["sha256"] or len(content) != asset["size_bytes"]:
            raise PreflightError("Dataset asset hash or size differs from its manifest.")
    return len(manifest["assets"])


def check_image(root: Path, image: str, expected: dict[str, str]) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/@-]{0,200}", image):
        raise PreflightError("Invalid local image reference.")
    image_id = (
        command(["docker", "image", "inspect", "--format", "{{.Id}}", image], root).decode().strip()
    )
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
        raise PreflightError("Could not resolve a local immutable image ID.")
    raw = command(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--entrypoint",
            "python",
            image_id,
            "-c",
            IMAGE_PROBE,
        ],
        root,
    )
    observed = json.loads(raw)
    # Docker build instructions/ignore files are not present in the installed image.
    installed = {
        path: value
        for path, value in expected.items()
        if path not in {"Dockerfile", ".dockerignore"}
    }
    drift = differences(installed, observed["files"])
    return {
        "image_id": image_id,
        "python_version": observed["python_version"],
        "matches_baseline": not drift,
        "different_files": drift,
    }


def inspect(root: Path = ROOT, image: str | None = None) -> dict[str, Any]:
    load_template(root)
    assets = check_dataset(root)
    expected = baseline_files(root)
    drift = differences(expected, local_files(root))
    image_result = check_image(root, image, expected) if image else None
    blockers = list(LIVE_BLOCKERS)
    if image_result is None:
        blockers.insert(0, "Dedicated benchmark image provenance has not been checked.")
    elif not image_result["matches_baseline"]:
        blockers.insert(0, "Installed image does not match the pinned V1 runtime.")
    if drift:
        blockers.insert(0, "Working-tree runtime inputs differ from the V1 baseline.")
    return {
        "schema_version": 1,
        "task_id": "V2-004",
        "evidence_lane": "offline_preflight",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "runtime_baseline_commit": BASELINE,
        "application_commit": command(["git", "rev-parse", "HEAD"], root).decode().strip(),
        "dataset_manifest_sha256": MANIFEST_HASH,
        "verified_fixture_assets": assets,
        "runtime_files_checked": len(expected),
        "runtime_matches_baseline": not drift,
        "different_files": drift,
        "uv_lock_sha256": expected["uv.lock"],
        "image": image_result,
        "collection_ready": False,
        "live_blockers": blockers,
        "measured_attempts": 0,
        "provider_calls": 0,
    }


def campaign_skeleton(
    template: dict[str, Any], report: dict[str, Any], name: str
) -> dict[str, Any]:
    # Round-trip copy so preparing a campaign cannot mutate the pinned input template.
    run: dict[str, Any] = json.loads(json.dumps(template))
    run.update(status="blocked", campaign_id=name, application_commit=report["application_commit"])
    run["environment"]["uv_lock_sha256"] = report["uv_lock_sha256"]
    run["limitations"] = [
        "Offline preparation only; no live campaign has started.",
        *report["live_blockers"],
        *run["limitations"][1:],
    ]
    run["attempts"] = [
        {
            "attempt_id": f"attempt-{round_index * 4 + probe_index + 1:02d}",
            "probe_id": probe,
            "round": round_index + 1,
            "status": "not_run",
            "started_at_utc": None,
            "ended_at_utc": None,
            "terminal_state": None,
            "failure_code": None,
            "expected_outcome_observed": None,
            "deletion_verified": None,
            "artifact_kinds": [],
            "metric_sample_counts": {},
            "review": [],
            "deviations": [],
        }
        for round_index in range(5)
        for probe_index, probe in enumerate(PROBES)
    ]
    return run


def prepare(root: Path, name: str, report: dict[str, Any]) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
        raise PreflightError("Campaign ID must be 1-64 lowercase letters, digits, or hyphens.")
    if not report["runtime_matches_baseline"]:
        raise PreflightError("Resolve local runtime drift before preparing this baseline campaign.")
    folder = root / "data" / "benchmarks" / name
    for path in (root / "data", root / "data/benchmarks", folder):
        if path.is_symlink():
            raise PreflightError("Campaign directories must not be symbolic links.")
    run = campaign_skeleton(load_template(root), report, name)
    archive = command(["git", "archive", "--format=tar", BASELINE, "--", *BUILD_PATHS], root)
    try:
        folder.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise PreflightError(
            "Campaign already exists; preparation never overwrites evidence."
        ) from error
    (folder / "run.json").write_text(json.dumps(run, indent=2) + "\n")
    (folder / "preflight.json").write_text(json.dumps(report, indent=2) + "\n")
    (folder / "build-context.tar").write_bytes(archive)
    (folder / "build-context.sha256").write_text(digest(archive) + "\n")
    return folder


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image", help="Inspect an existing local image without networking or mounts"
    )
    parser.add_argument(
        "--prepare", metavar="CAMPAIGN_ID", help="Create ignored, unscored preparation files"
    )
    args = parser.parse_args()
    try:
        report = inspect(image=args.image)
        if args.prepare:
            folder = prepare(ROOT, args.prepare, report)
            report["prepared_directory"] = folder.relative_to(ROOT).as_posix()
        print(json.dumps(report, indent=2))  # noqa: T201
        return (
            0
            if report["runtime_matches_baseline"]
            and (not report["image"] or report["image"]["matches_baseline"])
            else 1
        )
    except (PreflightError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        message = (
            str(error)
            if isinstance(error, PreflightError)
            else "Invalid or unavailable local preflight input."
        )
        print(  # noqa: T201
            json.dumps({"task_id": "V2-004", "collection_ready": False, "error": message}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
