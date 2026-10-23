"""What `codex_end` gives for a legacy Codex launcher whose transcript does not read or gives no Codex role."""

import json
import sys
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from operations.roles import CODEX_LAUNCHER
from tests.conftest import script

scripts_importable()
operator_state = script("operator_state")
codex_reads = sys.modules["codex_reads"]
state_reads = sys.modules["state_reads"]
transcripts = sys.modules["transcripts"]

LAUNCHER = "a0000000000000c01"


def launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entries: list[dict] | None) -> None:
    """A launcher whose transcript is under `tmp_path`: absent where `entries` is None."""
    path = tmp_path / "p" / "s" / "subagents" / f"agent-{LAUNCHER}.jsonl"
    path.parent.mkdir(parents=True)
    path.with_suffix(".meta.json").write_text(json.dumps({"agentType": CODEX_LAUNCHER,
                                                          "description": "x"}))
    if entries is not None:
        path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    monkeypatch.setattr(transcripts, "project_dirs", lambda: [tmp_path])
    monkeypatch.setattr(operator_state, "launched_find", lambda aid: path)
    monkeypatch.setitem(codex_reads._native_sessions, LAUNCHER, tmp_path)
    state_reads.new_state()


def test_a_transcript_that_does_not_read_gives_its_error_alone(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    launcher(tmp_path, monkeypatch, None)
    read = operator_state.codex_end(LAUNCHER, tmp_path)
    assert read.end is operator_state.CodexEnd.UNKNOWN
    assert "; " not in read.why and "agent-" in read.why


def test_a_launcher_whose_first_prompt_gives_no_role_is_dead(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    launcher(tmp_path, monkeypatch, [{"type": "user", "message": {"content": "hello"}}])
    read = operator_state.codex_end(LAUNCHER, tmp_path)
    assert read.end is operator_state.CodexEnd.DEAD
    assert "gives no Codex role" in read.why
