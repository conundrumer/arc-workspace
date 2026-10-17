"""The hook that holds an agent with a report file to it: a handback that
passes with the reply sent elsewhere leaves the operator reading no reply,
and nothing in the run shows it."""

import json
from pathlib import Path

from engine import checkout
from handbook.paths import scripts_importable
from tests.hookrun import run_hook

scripts_importable()

AGENT = "a0000000000000001"
HOOK = checkout.scripts() / "report_file_hook.py"
NAME = "11-485-0123456789ab-reply.txt"


def session(tmp_path: Path, message: str) -> str:
    """A session whose agent `AGENT` got a filed brief that gives a report
    file under `tmp_path`, and the hook input of its SubagentHandback call
    with `message`."""
    agents = tmp_path / "s" / "subagents"
    agents.mkdir(parents=True)
    filed = tmp_path / "brief.md"
    filed.write_text(f"Do the work.\nReport file: `{tmp_path / NAME}`.\n")
    lines = [{"type": "user", "uuid": "u0", "message": {"content": [{"type": "text", "text":
             f"Read the file {filed} first: it holds the text of this message."}]}}]
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
    (tmp_path / NAME).write_text("done\n")
    assert not denied(stdin)
