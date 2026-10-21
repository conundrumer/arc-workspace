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
    with pytest.raises((OSError, ValueError, KeyError)):
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


PREPARATION_TRACEBACK = '''Traceback (most recent call last):
  File "/repo/scripts/codex_agent.py", line 397, in <module>
    sys.exit(main(sys.argv[1:]))
  File "/repo/scripts/codex_agent.py", line 379, in main
    message = run(args.agent, args.scratch, args.brief, args.model, args.effort,
  File "/repo/scripts/codex_agent.py", line 296, in run
    instructions = None if thread is not None else role_instructions(root, home, agent, agent_type)
  File "/repo/scripts/codex_agent.py", line 98, in role_instructions
    entry_text(user.resolve())
  File "/repo/src/controlled_markdown/parser.py", line 224, in parse
    raise ControlledMarkdownError(source, num, Rule.NO_MARKER,
controlled_markdown.nodes.ControlledMarkdownError: /home/.claude/CLAUDE.md:3: no-marker: bad line

[exited with code 1]'''


def preparation_failure(tmp_path, *, background=False, output=PREPARATION_TRACEBACK):
    """A launch with no record, followed by its foreground or background result."""
    command = f"uv run python scripts/codex_agent.py code-reviewer {tmp_path} /tmp/b model high"
    launch = {"type": "assistant", "timestamp": "2026-10-20T00:00:00Z", "message": {
        "content": [{"type": "tool_use", "name": "Bash", "id": "failed",
                     "input": {"command": command}}]}}
    if background:
        path = tmp_path / "background.output"
        path.write_text(output)
        output = f"Command running in background. Output is being written to: {path}."
    result = {"type": "user", "message": {"content": [{
        "type": "tool_result", "tool_use_id": "failed", "content": output}]}}
    return launch, result


@pytest.mark.parametrize("position", ["alone", "before", "between", "after"])
@pytest.mark.parametrize("reason", [
    "This call was not run, since your documents may have changed.",
    "Repository edits must use the delegated agent.",
    "A different hook declined this command.",
])
def test_hook_refused_bash_adds_no_walk(tmp_path, position, reason):
    refused, result = preparation_failure(tmp_path, output="PreToolUse:Bash hook error: " + reason)
    refused["timestamp"] = "2026-10-20T00:00:05Z"
    refused["message"]["content"][0]["input"]["command"] += " --resume"
    result["message"]["content"][0]["is_error"] = True
    entries = [refused, result]
    expected = []
    if position != "alone":
        first = turn(tmp_path, [(STEP, "first")])
        first["timestamp"] = "2026-10-20T00:00:00Z"
        path = tmp_path / "codex-events.jsonl"
        record = json.loads(path.read_text())
        # A refused call cannot bound the accepted call's preparation time.
        record["started"] = 1792454410
        path.write_text(json.dumps(record) + "\n")
        if position == "before":
            refused["timestamp"] = "2026-10-19T23:59:59Z"
            entries.append(first)
        else:
            entries.insert(0, first)
        expected = [("1:0", "first")]
    if position == "between":
        retry = turn(tmp_path, [(STEP, "resumed")], first=False)
        retry["timestamp"] = "2026-10-20T00:01:00Z"
        retry["message"]["content"][0]["id"] = "retry"
        entries.append(retry)
        expected.append(("2:0", "resumed"))
    original = json.dumps(entries)
    assert walk.step_calls(reads.walk_entries(entries, "code-reviewer"), "code-reviewer") == expected
    assert json.dumps(entries) == original


@pytest.mark.parametrize("command", [
    "uv run python scripts/codex_agent.py",
    "uv run python scripts/codex_agent.py code-editor /missing /tmp/b model high",
    "uv run python scripts/codex_agent.py code-reviewer /missing /tmp/b model high\n"
    "uv run python scripts/codex_agent.py code-reviewer /other /tmp/b model high",
])
def test_hook_refusal_skips_whole_bash_call_but_keeps_other_blocks(tmp_path, command):
    refused, result = preparation_failure(tmp_path, output="PreToolUse:Bash hook error: declined")
    refused["message"]["content"][0]["input"]["command"] = command
    result["message"]["content"][0]["is_error"] = True
    accepted = turn(tmp_path, [(STEP, "accepted")])
    refused["message"]["content"].extend(accepted["message"]["content"])
    prompt = {"type": "text", "text": "Continue the walk."}
    result["message"]["content"].append(prompt)
    entries = reads.walk_entries([refused, result], "code-reviewer")
    assert walk.step_calls(entries, "code-reviewer") == [("1:0", "accepted")]
    assert entries[-1] == result


@pytest.mark.parametrize("bad", ["wrong-id", "not-error", "missing-error", "post-hook", "quoted"])
def test_unproved_hook_refusal_still_requires_turn_record(tmp_path, bad):
    accepted = turn(tmp_path, [(STEP, "completed")])
    refused, result = preparation_failure(tmp_path, output="PreToolUse:Bash hook error: declined")
    refused["message"]["content"][0]["input"]["command"] += " --resume"
    block = result["message"]["content"][0]
    block["is_error"] = True
    match bad:
        case "wrong-id":
            block["tool_use_id"] = "other"
        case "not-error":
            block["is_error"] = False
        case "missing-error":
            del block["is_error"]
        case "post-hook":
            block["content"] = "PostToolUse:Bash hook error: declined"
        case "quoted":
            block["content"] = "Command output: " + block["content"]
    with pytest.raises(ValueError, match="no turn record"):
        reads.walk_entries([accepted, refused, result], "code-reviewer")


@pytest.mark.parametrize("background", [False, True])
@pytest.mark.parametrize("retry", [False, True])
@pytest.mark.parametrize("diagnostic", [False, True])
def test_unrecorded_preparation_failure_adds_no_walk_and_allows_retry(
        tmp_path, background, retry, diagnostic):
    output = ("codex_agent: /home/CLAUDE.md:3: no-marker: bad line\n\n[exited with code 1]"
              if diagnostic else PREPARATION_TRACEBACK)
    entries = list(preparation_failure(tmp_path, background=background, output=output))
    expected = []
    if retry:
        accepted = turn(tmp_path, [(STEP, "actual turn")])
        accepted["timestamp"] = "2026-10-20T00:01:00Z"
        path = tmp_path / "codex-events.jsonl"
        record = json.loads(path.read_text())
        record.update(started=1792454461, ended=1792454462)
        path.write_text(json.dumps(record) + "\n")
        entries.append(accepted)
        expected = [("1:0", "actual turn")]
    assert walk.step_calls(reads.walk_entries(entries, "code-reviewer"), "code-reviewer") == expected


@pytest.mark.parametrize("bad", ["post-start", "wrong-id", "missing-output",
                                 "untimed-record", "overlapping-record", "multiple-launches",
                                 "resume", "session-only"])
def test_unproved_missing_record_still_refuses(tmp_path, bad):
    failed, result = preparation_failure(tmp_path, background=True)
    retry = turn(tmp_path, [(STEP, "must not hide missing evidence")])
    retry["timestamp"] = "2026-10-20T00:01:00Z"
    path = tmp_path / "codex-events.jsonl"
    record = json.loads(path.read_text())
    record.update(started=1792454461, ended=1792454462)
    output = tmp_path / "background.output"
    match bad:
        case "post-start":
            output.write_text(PREPARATION_TRACEBACK.replace("in role_instructions", "in daemon_turn"))
        case "wrong-id":
            result["message"]["content"][0]["tool_use_id"] = "unrelated"
        case "missing-output":
            output.unlink()
        case "untimed-record":
            del record["started"]
        case "overlapping-record":
            record["started"] = 1792454401
        case "multiple-launches":
            block = failed["message"]["content"][0]
            block["input"]["command"] += "\n" + block["input"]["command"]
        case "resume":
            failed["message"]["content"][0]["input"]["command"] += " --resume"
        case "session-only":
            path.unlink()
            with pytest.raises(ValueError, match="no turn record"):
                reads.walk_entries([failed, result], "code-reviewer")
            return
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match="no (matching )?turn record|more than one Codex command"):
        reads.walk_entries([failed, result, retry], "code-reviewer")


@pytest.mark.parametrize("pipe", ["tail -5", "cat", "tee /tmp/launch.log", "sed -n '1,5p'"])
@pytest.mark.parametrize("output", [
    "\n".join(PREPARATION_TRACEBACK.splitlines()[-6:-2]),
    "custom.setup.ConfigurationError: missing settings",
    "codex_agent: failed\n\n[exited with code 1]",
    "Exit code 2\ncannot open brief",
])
@pytest.mark.parametrize("retry", [False, True])
def test_filtered_unrecorded_failure_adds_nothing(tmp_path, pipe, output, retry):
    failed, result = preparation_failure(tmp_path, output=output)
    failed["message"]["content"][0]["input"]["command"] += f" <<'INPUT' 2>&1 | {pipe}\nwork\nINPUT"
    entries = [failed, result]
    expected = []
    if retry:
        accepted = turn(tmp_path, [(STEP, "completed")])
        accepted["timestamp"] = "2026-10-20T00:01:00Z"
        path = tmp_path / "codex-events.jsonl"
        record = json.loads(path.read_text())
        record.update(started=1792454461, ended=1792454462)
        path.write_text(json.dumps(record) + "\n")
        entries.append(accepted)
        expected = [("1:0", "completed")]
    assert walk.step_calls(reads.walk_entries(entries, "code-reviewer"), "code-reviewer") == expected


@pytest.mark.parametrize("output", ["", "failed", "completed", "Traceback (most recent call last):"])
def test_filtered_output_without_failure_evidence_still_refuses(tmp_path, output):
    failed, result = preparation_failure(tmp_path, output=output)
    failed["message"]["content"][0]["input"]["command"] += " 2>&1 | tail -5"
    with pytest.raises((OSError, ValueError)):
        reads.walk_entries([failed, result], "code-reviewer")


def test_failed_tool_result_without_a_turn_adds_nothing(tmp_path):
    failed, result = preparation_failure(tmp_path, output="")
    result["message"]["content"][0]["is_error"] = True
    assert reads.walk_entries([failed, result], "code-reviewer") == []


def test_filtered_failure_cannot_discard_its_turn_record(tmp_path):
    failed, result = preparation_failure(tmp_path, output="custom.Error: failed")
    turn(tmp_path, [(STEP, "recorded")])
    assert walk.step_calls(reads.walk_entries([failed, result], "code-reviewer"),
                           "code-reviewer") == [("1:0", "recorded")]


def test_timed_preparation_failure_cannot_discard_a_matching_turn_record(tmp_path):
    failed, result = preparation_failure(tmp_path, output="")
    result["timestamp"] = "2026-10-20T00:00:10Z"
    (tmp_path / "codex-launch-failures.jsonl").write_text(json.dumps({
        "id": "a" * 32, "error": "cannot prepare", "started": 1792454401, "ended": 1792454402}))
    turn(tmp_path, [(STEP, "recorded")])
    path = tmp_path / "codex-events.jsonl"
    record = json.loads(path.read_text())
    record.update(started=1792454401, ended=1792454402)
    path.write_text(json.dumps(record) + "\n")
    assert walk.step_calls(reads.walk_entries([failed, result], "code-reviewer"),
                           "code-reviewer") == [("1:0", "recorded")]


def test_failure_after_a_completed_call_keeps_its_walk(tmp_path):
    accepted = turn(tmp_path, [(STEP, "completed")])
    failed, result = preparation_failure(tmp_path, output="Exit code 2\nmissing brief")
    assert walk.step_calls(reads.walk_entries([accepted, failed, result], "code-reviewer"),
                           "code-reviewer") == [("1:0", "completed")]


@pytest.mark.parametrize("output", [
    '{"type":"turn.started"}\n\n[exited with code 1]',
    "codex_agent: daemon turn failed (not replayed): disconnected\n\n[exited with code 1]",
    "codex_agent: codex exec exited 1 with no last message or thread id\n\n[exited with code 1]",
])
def test_turn_execution_without_a_record_still_refuses(tmp_path, output):
    failed, result = preparation_failure(tmp_path, output=output)
    with pytest.raises((OSError, ValueError)):
        reads.walk_entries([failed, result], "code-reviewer")


@pytest.mark.parametrize("pipe", ["tail -1", "head -1", "cat >/dev/null"])
@pytest.mark.parametrize("proof", ["valid", "earlier", "later", "overlap", "untimed", "duplicate"])
@pytest.mark.parametrize("background", [False, True])
def test_saved_preparation_failure_survives_output_filters(tmp_path, pipe, proof, background):
    failed, result = preparation_failure(tmp_path, output="", background=background)
    failed["message"]["content"][0]["input"]["command"] += f" --resume 2>&1 | {pipe}"
    result["timestamp"] = "2026-10-20T00:00:10Z"
    entries = [failed, result]
    if background:
        result["timestamp"] = "2026-10-20T00:00:00.500Z"
        entries.append({"type": "assistant", "timestamp": "2026-10-20T00:00:10Z",
                        "message": {"content": "Preparation ended."}})
    saved = {"id": "a" * 32, "error": "cannot prepare", "started": 1792454401, "ended": 1792454402}
    match proof:
        case "earlier":
            saved.update(started=1792454398, ended=1792454399)
        case "later":
            saved.update(started=1792454411, ended=1792454412)
        case "overlap":
            saved.update(started=1792454399)
        case "untimed":
            del saved["started"]
    (tmp_path / "codex-launch-failures.jsonl").write_text(
        (json.dumps(saved) + "\n") * (2 if proof == "duplicate" else 1))
    if proof == "valid":
        assert reads.walk_entries(entries, "code-reviewer") == []
    else:
        with pytest.raises((OSError, ValueError)):
            reads.walk_entries(entries, "code-reviewer")


def test_exhausted_records_name_the_unaccounted_launch(tmp_path):
    first = turn(tmp_path, [])
    second = json.loads(json.dumps(first))
    second["message"]["content"][0]["id"] = "missing-launch"
    with pytest.raises(ValueError, match="launch missing-launch has no turn record"):
        reads.walk_entries([first, second], "code-reviewer")


@pytest.mark.parametrize("proof", ["valid", "missing", "wrong-id", "wrong-error", "duplicate",
                                   "bad-times", "extra-output"])
def test_identified_preparation_failure_requires_its_saved_evidence(tmp_path, proof):
    accepted = turn(tmp_path, [(STEP, "completed")])
    token = "a" * 32
    output = f"codex_agent: launch failed before Codex started [{token}]: unavailable git directory"
    failed, result = preparation_failure(tmp_path, output=output)
    failed["message"]["content"][0]["input"]["command"] += " --resume"
    saved = {"id": token, "error": "unavailable git directory", "started": 1, "ended": 2}
    match proof:
        case "wrong-id":
            saved["id"] = "b" * 32
        case "wrong-error":
            saved["error"] = "different error"
        case "bad-times":
            saved["ended"] = 0
        case "extra-output":
            result["message"]["content"][0]["content"] = "accepted turn\n" + output
    if proof != "missing":
        (tmp_path / "codex-launch-failures.jsonl").write_text(
            (json.dumps(saved) + "\n") * (2 if proof == "duplicate" else 1))
    if proof == "valid":
        assert walk.step_calls(reads.walk_entries([accepted, failed, result], "code-reviewer"),
                               "code-reviewer") == [("1:0", "completed")]
    else:
        with pytest.raises(ValueError, match="no turn record"):
            reads.walk_entries([accepted, failed, result], "code-reviewer")


def test_hook_refusal_is_removed_from_call_enumeration(tmp_path):
    refused = turn(tmp_path, [])
    refused['message']['content'][0]['id'] = 'blocked'
    refused['message']['content'][0]['input']['command'] = 'uv run python scripts/codex_agent.py broken'
    proof = {'type': 'user', 'message': {'content': [{'type': 'tool_result',
        'tool_use_id': 'blocked', 'is_error': True,
        'content': 'PreToolUse:Bash hook error: blocked'}]}}
    retry = turn(tmp_path, [(STEP, 'accepted')])
    entries = [refused, proof, retry]
    assert [c.call_id for c in reads.calls(entries)] == ['codex']
    assert walk.step_calls(reads.walk_entries(entries, 'code-reviewer'), 'code-reviewer') == [
        ('1:0', 'accepted')]


@pytest.mark.parametrize('bad', [None, 'missing-result', 'wrong-interval', 'wrong-thread', 'wrong-turn', 'ended'])
def test_live_baseline_uses_only_completed_commands_of_current_turn(tmp_path, bad):
    entry = turn(tmp_path, [])
    entry['timestamp'] = '2026-10-20T00:00:00Z'
    (tmp_path / 'codex-events.jsonl').unlink()
    directory = tmp_path / '.codex' / 'sessions'
    directory.mkdir(parents=True)
    rows = [
        {'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': 'current'}},
        {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command',
            'call_id': 'step', 'arguments': json.dumps({'cmd': STEP})}},
        {'type': 'response_item', 'payload': {'type': 'function_call_output',
            'call_id': 'step', 'output': 'completed item'}},
        {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'exec_command',
            'call_id': 'pending', 'arguments': json.dumps({'cmd': STEP})}},
    ]
    if bad == 'missing-result':
        rows.pop(2)
    if bad == 'wrong-turn':
        rows.append({'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': 'other'}})
    if bad == 'ended':
        rows.append({'type': 'event_msg', 'payload': {'type': 'task_complete', 'turn_id': 'current'}})
    stamp = '2026-10-19T00:00:01Z' if bad == 'wrong-interval' else '2026-10-20T00:00:01Z'
    path = directory / ('rollout-now-other.jsonl' if bad == 'wrong-thread' else 'rollout-now-thread.jsonl')
    path.write_text(''.join(json.dumps({'timestamp': stamp, **row}) + '\n' for row in rows)
                    + '{"partial":')
    if bad in ('wrong-thread', 'wrong-interval', 'wrong-turn', 'ended'):
        with pytest.raises(ValueError):
            reads.baseline_entries([entry], 'code-reviewer', tmp_path)
    else:
        results = walk.step_calls(reads.baseline_entries([entry], 'code-reviewer', tmp_path),
                                  'code-reviewer')
        assert results == ([] if bad else [('step', 'completed item')])
    with pytest.raises(ValueError):
        reads.walk_entries([entry], 'code-reviewer')
