"""V2-004 checks fail closed and never import provider configuration."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_preflight", ROOT / "benchmarks/preflight.py"
)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


@pytest.fixture
def inputs(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "benchmarks/fixtures", tmp_path / "benchmarks/fixtures")
    shutil.copy(ROOT / "benchmarks/run-template.json", tmp_path / "benchmarks/run-template.json")
    return tmp_path


def report() -> dict[str, object]:
    return {
        "runtime_matches_baseline": True,
        "application_commit": "a" * 40,
        "uv_lock_sha256": "b" * 64,
        "live_blockers": list(preflight.LIVE_BLOCKERS),
    }


def test_pinned_fixture_and_protocol_integrity(inputs: Path) -> None:
    assert preflight.check_dataset(inputs) == 9
    assert preflight.load_template(inputs)["runtime_baseline_commit"] == preflight.BASELINE


@pytest.mark.parametrize("key", ["stt_model", "meet_attempt_hourly_limit", "duration_minutes"])
def test_any_template_configuration_drift_is_rejected(inputs: Path, key: str) -> None:
    path = inputs / "benchmarks/run-template.json"
    changed = json.loads(path.read_text())
    changed["configuration"][key] = 0
    path.write_text(json.dumps(changed))
    with pytest.raises(preflight.PreflightError, match="pinned protocol"):
        preflight.load_template(inputs)


@pytest.mark.parametrize("asset", ["manifest.json", "audio/answer.wav", "resume.txt"])
def test_damaged_or_replaced_fixtures_block_preflight(inputs: Path, asset: str) -> None:
    path = inputs / "benchmarks/fixtures/v1" / asset
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(preflight.PreflightError, match="differs"):
        preflight.check_dataset(inputs)


def test_fixture_symlink_is_rejected_even_with_matching_bytes(inputs: Path) -> None:
    path = inputs / "benchmarks/fixtures/v1/resume.txt"
    destination = inputs / "outside.txt"
    path.rename(destination)
    path.symlink_to(destination)
    with pytest.raises(preflight.PreflightError, match="escapes"):
        preflight.check_dataset(inputs)


def test_detects_added_removed_and_changed_runtime_inputs(inputs: Path) -> None:
    (inputs / "src").mkdir()
    (inputs / "src/new.py").write_text("new")
    (inputs / "uv.lock").write_text("updated")
    actual = preflight.local_files(inputs)
    assert preflight.differences({"src/old.py": "old", "uv.lock": "old"}, actual) == [
        "src/new.py",
        "src/old.py",
        "uv.lock",
    ]


def test_runtime_symlinks_fail_closed(inputs: Path) -> None:
    (inputs / "uv.lock").symlink_to(inputs / "benchmarks/run-template.json")
    with pytest.raises(preflight.PreflightError, match="symbolic"):
        preflight.local_files(inputs)


def test_campaign_skeleton_preserves_all_twenty_unrun_attempts(inputs: Path) -> None:
    template = preflight.load_template(inputs)
    run = preflight.campaign_skeleton(template, report(), "test-campaign")
    assert run["status"] == "blocked"
    assert run["started_at_utc"] is None
    assert run["budget"]["provider_cap"] is None
    assert run["warmup"] == {"status": "not_run", "cost": None}
    assert run["results"]["reliability"] is None
    assert run["results"]["provider_cost"] is None
    assert len(run["attempts"]) == 20
    assert [item["attempt_id"] for item in run["attempts"]] == [
        f"attempt-{index:02d}" for index in range(1, 21)
    ]
    assert [item["probe_id"] for item in run["attempts"]] == list(preflight.PROBES) * 5
    assert [item["round"] for item in run["attempts"]] == [i // 4 + 1 for i in range(20)]
    assert all(item["status"] == "not_run" for item in run["attempts"])
    assert all(item["expected_outcome_observed"] is None for item in run["attempts"])
    assert template["attempts"] == []
    assert template["status"] == "template"


@pytest.mark.parametrize(
    "name", ["../escape", "/outside/escape", "", "campaign with spaces", "a" * 65]
)
def test_unsafe_campaign_names_cannot_write(inputs: Path, name: str) -> None:
    with pytest.raises(preflight.PreflightError, match="Campaign ID"):
        preflight.prepare(inputs, name, report())
    assert not (inputs / "data").exists()


def test_preparation_does_not_overwrite_or_follow_symlinks(
    inputs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preflight, "command", lambda *_: b"public pinned archive")
    folder = preflight.prepare(inputs, "campaign", report())
    original = (folder / "run.json").read_bytes()
    with pytest.raises(preflight.PreflightError, match="never overwrites"):
        preflight.prepare(inputs, "campaign", report())
    assert (folder / "run.json").read_bytes() == original
    (inputs / "data/benchmarks/alias").symlink_to(folder)
    with pytest.raises(preflight.PreflightError, match="symbolic"):
        preflight.prepare(inputs, "alias", report())


def test_prepare_refuses_local_drift_before_writing(inputs: Path) -> None:
    changed = report() | {"runtime_matches_baseline": False}
    with pytest.raises(preflight.PreflightError, match="runtime drift"):
        preflight.prepare(inputs, "campaign", changed)
    assert not (inputs / "data").exists()


def test_archive_is_taken_from_pinned_git_not_working_tree(
    inputs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = []

    def capture(args: list[str], root: Path) -> bytes:
        commands.append(args)
        return b"pinned source archive"

    monkeypatch.setattr(preflight, "command", capture)
    folder = preflight.prepare(inputs, "campaign", report())
    assert commands == [
        ["git", "archive", "--format=tar", preflight.BASELINE, "--", *preflight.BUILD_PATHS]
    ]
    assert (folder / "build-context.tar").read_bytes() == b"pinned source archive"
    assert (folder / "build-context.sha256").read_text().strip() == preflight.digest(
        b"pinned source archive"
    )


def test_image_probe_is_networkless_readonly_and_uses_immutable_id(
    inputs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = []
    image_id = "sha256:" + "a" * 64
    expected = {"src/runtime.py": "hash", "uv.lock": "lock", "Dockerfile": "build"}

    def capture(args: list[str], root: Path) -> bytes:
        commands.append(args)
        if args[1:3] == ["image", "inspect"]:
            return image_id.encode()
        return json.dumps(
            {"files": {"src/runtime.py": "hash", "uv.lock": "lock"}, "python_version": "3.12.13"}
        ).encode()

    monkeypatch.setattr(preflight, "command", capture)
    result = preflight.check_image(inputs, "local-image:tag", expected)
    assert result["matches_baseline"]
    invocation = commands[1]
    assert invocation[invocation.index("--network") + 1] == "none"
    assert "--read-only" in invocation
    assert invocation[invocation.index("--entrypoint") + 1] == "python"
    assert image_id in invocation
    assert not any(arg in invocation for arg in ["-v", "--volume", "--env", "--env-file"])


def test_image_drift_does_not_pass(inputs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def capture(args: list[str], root: Path) -> bytes:
        if args[1:3] == ["image", "inspect"]:
            return ("sha256:" + "a" * 64).encode()
        return json.dumps({"files": {"uv.lock": "changed"}, "python_version": "3.12.13"}).encode()

    monkeypatch.setattr(preflight, "command", capture)
    result = preflight.check_image(inputs, "image:tag", {"uv.lock": "pinned"})
    assert result["matches_baseline"] is False
    assert result["different_files"] == ["uv.lock"]


def test_subprocess_failures_do_not_echo_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, "git", stderr=b"synthetic-private-canary")

    monkeypatch.setattr(preflight.subprocess, "run", fail)
    with pytest.raises(preflight.PreflightError) as error:
        preflight.command(["git", "status"], ROOT)
    assert "synthetic-private-canary" not in str(error.value)


def test_successful_offline_check_never_claims_collection_readiness(
    inputs: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preflight, "baseline_files", lambda _: {"uv.lock": "pinned"})
    monkeypatch.setattr(preflight, "local_files", lambda _: {"uv.lock": "pinned"})
    monkeypatch.setattr(preflight, "command", lambda *_: b"a" * 40)
    checked = preflight.inspect(inputs)
    assert checked["runtime_matches_baseline"]
    assert checked["collection_ready"] is False
    assert checked["measured_attempts"] == 0
    assert checked["provider_calls"] == 0
    assert len(checked["live_blockers"]) >= 4


def test_runtime_directory_symlinks_are_not_traversed(inputs: Path) -> None:
    (inputs / "src").symlink_to(inputs / "benchmarks", target_is_directory=True)
    with pytest.raises(preflight.PreflightError, match="symbolic"):
        preflight.local_files(inputs)


def test_baseline_inventory_reads_pinned_git_blobs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def capture(args: list[str], root: Path) -> bytes:
        calls.append(args)
        if args[1] == "ls-tree":
            return b"src/runtime.py\0uv.lock\0"
        return b"pinned file contents"

    monkeypatch.setattr(preflight, "command", capture)
    files = preflight.baseline_files(ROOT)
    assert files == {
        "src/runtime.py": preflight.digest(b"pinned file contents"),
        "uv.lock": preflight.digest(b"pinned file contents"),
    }
    assert calls[1:] == [
        ["git", "show", f"{preflight.BASELINE}:src/runtime.py"],
        ["git", "show", f"{preflight.BASELINE}:uv.lock"],
    ]
