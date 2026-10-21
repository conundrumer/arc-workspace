"""The hook that holds an agent with a report file to it: a handback that
passes with the reply sent elsewhere leaves the operator reading no reply,
and nothing in the run shows it."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine import checkout
from handbook.checklist import Checklist
from handbook.paths import scripts_importable
from tests.hookrun import run_hook
from tests.codex_run import turn

scripts_importable()

AGENT = "a0000000000000001"
HOOK = checkout.scripts() / "report_file_hook.py"
NAME = "11-485-0123456789ab-reply.txt"
BRIEF_AT = 1_000_000_000.0


def at(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).isoformat().replace("+00:00", "Z")


def prompt(uuid: str, t: float, text: str) -> dict[str, object]:
    return {"type": "user", "uuid": uuid, "timestamp": at(t),
            "message": {"content": [{"type": "text", "text": text}]}}


def written(tmp_path: Path, t: float) -> None:
    """The report file under `tmp_path`, last written at `t`."""
    (tmp_path / NAME).write_text("done\n")
    os.utime(tmp_path / NAME, (t, t))


def session(tmp_path: Path, message: str, *later: dict[str, object]) -> str:
    """A session whose agent `AGENT` got, at `BRIEF_AT`, a filed brief that
    gives a report file under `tmp_path`, and then the entries `later`, and
    the hook input of its SubagentHandback call with `message`."""
    agents = tmp_path / "s" / "subagents"
    agents.mkdir(parents=True)
    filed = tmp_path / "brief.md"
    filed.write_text(f"Do the work.\nReport file: `{tmp_path / NAME}`.\n")
    lines = [prompt("u0", BRIEF_AT, f"Read the file {filed} first: it holds the text of this message."),
             *later]
    (agents / f"agent-{AGENT}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in lines))
    (tmp_path / "s.jsonl").write_text("")
    return json.dumps({"tool_name": "SubagentHandback", "agent_id": AGENT,
                       "transcript_path": str(tmp_path / "s.jsonl"),
                       "tool_input": {"message": message}})


def denied(stdin: str) -> bool:
    code, out, err = run_hook(HOOK, stdin)
    assert code == 0 and "failed" not in err, err
    return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_reply_sent_elsewhere_is_denied_once(tmp_path: Path) -> None:
    stdin = session(tmp_path, "My final reply went to a1 by SendMessage.")
    assert denied(stdin)
    assert not denied(stdin)


def test_the_path_of_a_file_not_there_is_denied(tmp_path: Path) -> None:
    assert denied(session(tmp_path, str(tmp_path / NAME)))


def test_the_path_of_the_written_file_is_allowed(tmp_path: Path) -> None:
    stdin = session(tmp_path, str(tmp_path / NAME))
    written(tmp_path, BRIEF_AT + 10)
    assert not denied(stdin)


def test_a_file_written_before_the_last_message_is_denied(tmp_path: Path) -> None:
    written(tmp_path, BRIEF_AT + 10)
    assert denied(session(tmp_path, str(tmp_path / NAME),
                          prompt("u1", BRIEF_AT + 20, "Review round 2.")))


def test_a_file_written_after_the_last_message_is_allowed(tmp_path: Path) -> None:
    written(tmp_path, BRIEF_AT + 30)
    assert not denied(session(tmp_path, str(tmp_path / NAME),
                              prompt("u1", BRIEF_AT + 20, "Review round 2.")))


def test_a_notification_after_the_write_is_allowed(tmp_path: Path) -> None:
    written(tmp_path, BRIEF_AT + 10)
    note = "<task-notification><status>completed</status></task-notification>"
    assert not denied(session(tmp_path, str(tmp_path / NAME), prompt("u1", BRIEF_AT + 20, note)))


def test_a_harness_note_after_the_write_is_allowed(tmp_path: Path) -> None:
    written(tmp_path, BRIEF_AT + 10)
    note = {**prompt("u1", BRIEF_AT + 20, "[handback-send-enforce] Your report has not been delivered."),
            "isMeta": True}
    assert not denied(session(tmp_path, str(tmp_path / NAME), note))


def test_a_launcher_is_held_to_its_report_file(tmp_path: Path) -> None:
    stdin = session(tmp_path, "done")
    meta = tmp_path / "s" / "subagents" / f"agent-{AGENT}.meta.json"
    meta.write_text(json.dumps({"agentType": "codex-launcher"}))
    assert denied(stdin)


def codex_session(tmp_path: Path, message: str, *later: dict[str, object]) -> str:
    stdin = session(tmp_path, message, *later)
    path = tmp_path / "s" / "subagents" / f"agent-{AGENT}.jsonl"
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    entries[0]["message"]["content"][0]["text"] += (
        "\nCodex mode: role `code-reviewer`, model `gpt-6.1-sol`, reasoning effort `medium`.")
    entries.append(turn(tmp_path / "codex", []))
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    path.with_suffix(".meta.json").write_text(json.dumps({"agentType": "codex-launcher"}))
    return stdin


def test_a_codex_report_written_after_the_last_message_is_allowed(tmp_path: Path) -> None:
    stdin = codex_session(tmp_path, str(tmp_path / NAME))
    written(tmp_path, BRIEF_AT + 10)
    assert not denied(stdin)


@pytest.mark.parametrize("hook_name", ["report_file_hook", "checklist_walk_hook"])
def test_handback_after_a_killed_launch_and_recorded_resume(tmp_path: Path, hook_name: str) -> None:
    stdin = codex_session(tmp_path, str(tmp_path / NAME))
    written(tmp_path, BRIEF_AT + 10)
    path = tmp_path / "s" / "subagents" / f"agent-{AGENT}.jsonl"
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    killed = entries[-1]
    killed["timestamp"] = at(BRIEF_AT + 1)
    killed["message"]["content"][0]["id"] = "killed"
    output = tmp_path / "killed.output"
    output.write_text("warning: environment mismatch\n\n[killed]\n")
    entries.append({"type": "user", "message": {"content": [{
        "type": "tool_result", "tool_use_id": "killed",
        "content": f"Output is being written to: {output}."}]}})
    checklist = Checklist("code-reviewer")
    results = [checklist.first(), *(checklist.after(i.heading.text) for i in checklist.items[:-1])]
    resumed = turn(tmp_path / "codex", [
        ("uv run python scripts/step.py code-reviewer", r) for r in results])
    resumed["timestamp"] = at(BRIEF_AT + 2)
    block = resumed["message"]["content"][0]
    block["id"] = "resumed"
    block["input"]["command"] = block["input"]["command"].replace(
        " <<'INPUT'", " --resume <<'INPUT'")
    entries.append(resumed)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    records = tmp_path / "codex" / "codex-events.jsonl"
    record = json.loads(records.read_text())
    record.update(started=BRIEF_AT + 3, ended=BRIEF_AT + 4)
    records.write_text(json.dumps(record) + "\n")
    code, out, err = run_hook(checkout.scripts() / f"{hook_name}.py", stdin)
    assert code == 0 and not out and "failed" not in err, (out, err)


def test_a_codex_report_before_a_resumed_message_is_denied_once(tmp_path: Path) -> None:
    stdin = codex_session(tmp_path, str(tmp_path / NAME), prompt("u1", BRIEF_AT + 20, "Continue."))
    written(tmp_path, BRIEF_AT + 10)
    assert denied(stdin)
    assert not denied(stdin)


def test_a_codex_report_with_missing_evidence_is_always_denied(tmp_path: Path) -> None:
    stdin = codex_session(tmp_path, str(tmp_path / NAME))
    written(tmp_path, BRIEF_AT + 10)
    (tmp_path / "codex" / "codex-events.jsonl").unlink()
    assert denied(stdin)
    assert denied(stdin)


def test_a_codex_report_with_an_unreadable_brief_is_always_denied(tmp_path: Path) -> None:
    stdin = codex_session(tmp_path, str(tmp_path / NAME))
    written(tmp_path, BRIEF_AT + 10)
    (tmp_path / "brief.md").unlink()
    assert denied(stdin)
    assert denied(stdin)
