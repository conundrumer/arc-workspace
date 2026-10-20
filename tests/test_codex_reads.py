"""Codex evidence must bind the walk to the launcher's completed turns."""

import json
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script
from tests.codex_run import turn

scripts_importable()
reads = script("codex_reads")
walk = script("checklist_walk_hook")
STEP = "uv run python scripts/step.py code-reviewer"


@pytest.mark.parametrize("option", ["--agent-type decision-analyst", "--agent-type=decision-analyst"])
def test_analyst_agent_type_option_forms(tmp_path: Path, option: str):
    step = "uv run python scripts/step.py decision-analyst"
    entry = turn(tmp_path, [(step, "item")])
    entry["message"]["content"][0]["input"]["command"] = (
        f"uv run python scripts/codex_agent.py ticket-analyst {tmp_path} /tmp/brief model high {option}")
    assert walk.step_calls(reads.walk_entries([entry], "decision-analyst"), "decision-analyst") == [
        ("1:0", "item")]


@pytest.mark.parametrize("bad", ["missing-session", "empty-session", "wrong-thread", "broken-json",
                                 "missing-turn", "extra-turn", "failed-turn", "unknown-events",
                                 "missing-output", "wrong-role", "missing-input", "non-text-input"])
def test_unreadable_evidence_is_refused(tmp_path: Path, bad: str):
    entries = [turn(tmp_path, [(STEP, "item")])]
    path = tmp_path / "codex-events.jsonl"
    record = json.loads(path.read_text())
    match bad:
        case "missing-session":
            (tmp_path / "codex-session").unlink()
        case "empty-session":
            (tmp_path / "codex-session").write_text("")
        case "wrong-thread":
            record["thread"] = "another"
        case "broken-json":
            record["output"] = "{"
        case "missing-turn":
            path.write_text("")
        case "extra-turn":
            turn(tmp_path, [], first=False)
        case "failed-turn":
            record["ok"] = False
        case "unknown-events":
            record["output"] = '{"type":"unknown"}'
        case "missing-output":
            record["output"] = json.dumps({"type": "item.completed", "item": {
                "type": "command_execution", "command": STEP}}) + '\n{"type":"turn.completed"}'
        case "missing-input":
            del record["input"]
        case "non-text-input":
            record["input"] = None
        case "wrong-role":
            entries[0]["message"]["content"][0]["input"]["command"] = (
                f"uv run python scripts/codex_agent.py code-editor {tmp_path} /tmp/b model high")
    if bad not in {"missing-turn", "extra-turn"}:
        path.write_text(json.dumps(record) + "\n")
    with pytest.raises((OSError, ValueError, KeyError, IndexError)):
        reads.walk_entries(entries, "code-reviewer")


def test_resumes_keep_command_order_and_can_recover_a_failed_turn(tmp_path: Path):
    entries = [turn(tmp_path, [(STEP, "first")])]
    path = tmp_path / "codex-events.jsonl"
    record = json.loads(path.read_text())
    record["ok"] = False
    path.write_text(json.dumps(record) + "\n")
    entries.append(turn(tmp_path, [(STEP, "second")], first=False))
    assert walk.step_calls(reads.walk_entries(entries, "code-reviewer"), "code-reviewer") == [
        ("1:0", "first"), ("2:0", "second")]


def test_a_failed_attempt_without_a_session_does_not_supply_walk_results(tmp_path: Path):
    first = turn(tmp_path, [(STEP, "ignored")])
    path = tmp_path / "codex-events.jsonl"
    record = json.loads(path.read_text())
    record.update(thread=None, ok=False)
    path.write_text(json.dumps(record) + "\n")
    entries = [first, turn(tmp_path, [(STEP, "first session result")], first=False)]
    assert walk.step_calls(reads.walk_entries(entries, "code-reviewer"), "code-reviewer") == [
        ("2:0", "first session result")]


@pytest.mark.parametrize("bad", ["successful-null", "null-after-session", "different-session"])
def test_no_session_failures_do_not_relax_session_checks(tmp_path: Path, bad: str):
    entries = [turn(tmp_path, [])]
    path = tmp_path / "codex-events.jsonl"
    record = json.loads(path.read_text())
    record.update(thread=None, ok=False)
    path.write_text(json.dumps(record) + "\n")
    entries.append(turn(tmp_path, [], first=False))
    records = [json.loads(line) for line in path.read_text().splitlines()]
    match bad:
        case "successful-null":
            records[0]["ok"] = True
        case "null-after-session":
            records.append(records[0])
            entries.append(entries[0])
        case "different-session":
            records[1]["thread"] = "other-session"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    with pytest.raises(ValueError):
        reads.walk_entries(entries, "code-reviewer")
