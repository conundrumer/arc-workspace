"""`scripts/heavy_command_hook.py` refuses a Bash or Monitor call that runs a
heavy command outside `run_heavy.py`, or inside it with a worker count over
its `--cpus`, and lets any other call through."""

import pytest

from handbook.paths import scripts_importable

scripts_importable()

from heavy_command_hook import check  # pyright: ignore[reportMissingImports]

GATE = "scripts/run_heavy.py"


def refused(command: str, tool: str = "Bash") -> bool:
    return check({"tool_name": tool, "tool_input": {"command": command}}) is not None


@pytest.mark.parametrize("command", [
    "cargo build --release",
    "cd engine && cargo +nightly test -p arclog",
    "maturin develop",
    "engine/target/release/arclog-cli check x",
    "uv run python -m arclog_convert.convert",
    "uv run python -m arclog_convert.lint --all",
    "uv run python engine/arclog-py/tables_export.py out",
    "timeout 60 uv run python engine/arclog-py/export_checks.py out --all",
    "python detectors.py cache export --workers 4",
    "python detectors.py cache export --workers=4",
    "cargo -j 4 tree",
    "cargo -j4 tree",
    "env FOO=1 cargo bench",
    "bash -c 'cd x; cargo clippy'",
    f"bash -c '{GATE} cargo build; cargo test'",
    f"{GATE} --cpus 2 bash -c 'cargo build -j 4'",
    f"{GATE} --cpus 2 python detectors.py cache --workers 3",
    f"timeout 60 {GATE} cargo test --jobs 2",
    f"{GATE} --cpus 4 --gib 8 python run.py --threads 5",
])
def test_a_heavy_command_outside_its_gate_or_over_its_cpus_is_refused(command):
    assert refused(command)


@pytest.mark.parametrize("command", [
    "cargo build --help",
    "cargo --version",
    "cargo fmt --check",
    "cargo -j 1 tree",
    "python detectors.py cache export --workers 1",
    "python detectors.py cache export --workers $N",
    "uv run pytest tests",
    "git status && ls",
    "bash -c 'echo hi; ls'",
    f"{GATE} cargo build",
    f"{GATE} --cpus 4 cargo build -j 4",
    f"timeout 60 {GATE} --cpus 8 --gib 12 uv run python -m arclog_convert.convert --workers 8",
    f"{GATE} --cpus 3 bash -c 'cd x; python detectors.py cache --workers 3; cargo test'",
    f"{GATE} bash -c 'cargo test --jobs=1'",
])
def test_any_other_command_is_let_through(command):
    assert not refused(command)


def test_a_monitor_call_is_checked_as_a_bash_call_is():
    assert refused("cargo build", tool="Monitor")
    assert not refused(f"{GATE} cargo build", tool="Monitor")


def test_the_refusal_of_an_over_count_gives_the_cpus_it_needs():
    reason = check({"tool_name": "Bash", "tool_input": {"command": f"{GATE} --cpus 2 cargo build -j 6"}})
    assert reason is not None and "--cpus 6" in reason


def test_the_joined_bash_hook_denies_a_heavy_command_outside_its_gate(monkeypatch):
    import json
    import sys

    from engine import checkout
    from tests.hookrun import run_hook

    joined = checkout.scripts() / "joined_hooks.py"
    monkeypatch.setattr(sys, "argv", [str(joined), "bash"])
    event = {"tool_name": "Bash", "tool_input": {"command": "cargo build"}}
    code, out, err = run_hook(joined, json.dumps(event), env={})
    assert code == 0, err
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
