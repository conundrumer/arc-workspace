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


@pytest.mark.parametrize("args", [
    "--help 2>&1 | head -40", "-h", "code-reviewer /tmp/unused /tmp/brief model high --help",
    "show /tmp/unused", "steer /tmp/unused 'keep going'", "interrupt /tmp/unused",
])
def test_commands_without_a_turn_do_not_consume_records(tmp_path: Path, args: str):
    inspection = {"type": "assistant", "message": {"content": [{
        "type": "tool_use", "name": "Bash", "id": "inspection",
        "input": {"command": f"uv run python scripts/codex_agent.py {args}"}}]}}
    assert list(reads.commands(inspection)) == []
    assert reads.walk_entries([inspection], "code-reviewer") == []
    first = turn(tmp_path, [(STEP, "first")])
    resumed = turn(tmp_path, [(STEP, "second")], first=False)
    entries = [inspection, first, inspection, resumed, inspection]
    assert walk.step_calls(reads.walk_entries(entries, "code-reviewer"), "code-reviewer") == [
        ("1:0", "first"), ("2:0", "second")]


def test_help_and_launch_in_one_bash_call(tmp_path: Path):
    entry = turn(tmp_path, [(STEP, "item")])
    block = entry["message"]["content"][0]
    block["input"]["command"] = (
        "uv run python scripts/codex_agent.py --help 2>&1 | head -40\n"
        + block["input"]["command"])
    assert walk.step_calls(reads.walk_entries([entry], "code-reviewer"), "code-reviewer") == [
        ("1:0", "item")]


@pytest.mark.parametrize("args", ["", "code-reviewer", "/tmp/brief model high",
                                 "code-reviewer /tmp/brief model high"])
def test_launch_without_role_or_scratch_still_refuses(tmp_path: Path, args: str):
    entry = turn(tmp_path, [(STEP, "item")])
    malformed = {"type": "assistant", "message": {"content": [{
        "type": "tool_use", "name": "Bash", "id": "malformed",
        "input": {"command": f"uv run python scripts/codex_agent.py {args}"}}]}}
    with pytest.raises(ValueError, match="no matching role and scratch directory"):
        reads.walk_entries([entry, malformed], "code-reviewer")


def test_help_word_after_option_terminator_is_a_launch_argument(tmp_path: Path):
    entry = turn(tmp_path, [(STEP, "item")])
    entry["message"]["content"][0]["input"]["command"] = (
        f"uv run python scripts/codex_agent.py code-reviewer {tmp_path} /tmp/brief -- --help high")
    assert walk.step_calls(reads.walk_entries([entry], "code-reviewer"), "code-reviewer") == [
        ("1:0", "item")]


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


@pytest.mark.parametrize("proof", ["refused", "exit-code", "missing", "accepted-output", "wrong-id"])
def test_refused_fresh_launch_can_retry_in_new_directory(tmp_path: Path, proof: str):
    old = tmp_path / "old"
    old.mkdir()
    first = turn(old, [(STEP, "unrelated")])
    content = "codex_agent: " + reads.FRESH_REFUSAL
    if proof == "exit-code":
        content = "Exit code 1\n" + content
    elif proof == "missing":
        content = "failed"
    elif proof == "accepted-output":
        content = "accepted thread\n" + content
    result = {"type": "user", "message": {"content": [{
        "type": "tool_result", "tool_use_id": "other" if proof == "wrong-id" else "codex",
        "content": content}]}}
    new = turn(tmp_path / "new", [(STEP, "accepted")])
    new["message"]["content"][0]["id"] = "retry"
    if proof in {"refused", "exit-code"}:
        assert walk.step_calls(reads.walk_entries([first, result, new], "code-reviewer"),
                               "code-reviewer") == [("1:0", "accepted")]
    else:
        with pytest.raises(ValueError):
            reads.walk_entries([first, result, new], "code-reviewer")


@pytest.mark.parametrize("extra", ["work", "show", "steer", "interrupt"])
def test_refusal_cannot_hide_multiple_codex_commands(tmp_path: Path, extra: str):
    first = turn(tmp_path / "old", [(STEP, "unrelated")])
    block = first["message"]["content"][0]
    command = block["input"]["command"]
    extra_command = command if extra == "work" else f"python scripts/codex_agent.py {extra}"
    block["input"]["command"] = command + "\n" + extra_command
    result = {"type": "user", "message": {"content": [{
        "type": "tool_result", "tool_use_id": "codex",
        "content": "codex_agent: " + reads.FRESH_REFUSAL}]}}
    retry = turn(tmp_path / "new", [(STEP, "accepted")])
    retry["message"]["content"][0]["id"] = "retry"
    with pytest.raises(ValueError, match="more than one Codex command"):
        reads.walk_entries([first, result, retry], "code-reviewer")


@pytest.mark.parametrize("session", [True, False])
def test_refusal_after_an_accepted_attempt_is_rejected(tmp_path: Path, session: bool):
    accepted = turn(tmp_path, [(STEP, "accepted")])
    if not session:
        path = tmp_path / "codex-events.jsonl"
        record = json.loads(path.read_text())
        record.update(thread=None, ok=False)
        path.write_text(json.dumps(record) + "\n")
        turn(tmp_path, [], first=False)
    refused = turn(tmp_path / "old", [(STEP, "unrelated")])
    refused["message"]["content"][0]["id"] = "refused"
    result = {"type": "user", "message": {"content": [{
        "type": "tool_result", "tool_use_id": "refused",
        "content": "codex_agent: " + reads.FRESH_REFUSAL}]}}
    with pytest.raises(ValueError, match="after an accepted Codex call"):
        reads.walk_entries([accepted, refused, result], "code-reviewer")
