"""The hooks that give a running reader the diff of its documents, run in
fresh processes as `.claude/settings.json` registers them. A lost update, an
update given twice, or a record that does not move gives no sign in use."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from engine import checkout

BEFORE = "9902f864930978d057225b591ef940510bfa6543"
EDITOR_ID = "a0123456789abcdef"
GENERAL_ID = "afedcba9876543210"


def head() -> str:
    return checkout.git_out(checkout.ROOT, "rev-parse", "HEAD").strip()


def command(event: str, matcher: str | None = None) -> str:
    settings = json.loads((checkout.claude() / "settings.json").read_text())
    [cmd] = [h["command"] for m in settings["hooks"][event]
             if m.get("matcher") == matcher for h in m["hooks"]]
    return cmd


def run(cmd: str, hook: dict[str, Any]) -> str:
    return subprocess.run(cmd, shell=True, input=json.dumps(hook),
                          capture_output=True, text=True, check=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(checkout.ROOT),
                               "CLAUDE_CODE_ENTRYPOINT": "cli"}).stdout


def line(**fields: Any) -> str:
    return json.dumps(fields) + "\n"


def session(tmp: Path) -> Path:
    main = tmp / "S.jsonl"
    main.write_text(line(parentUuid=None, type="user", uuid="u0"))
    subs = tmp / "S" / "subagents"
    subs.mkdir(parents=True)
    for aid, kind in [(EDITOR_ID, "code-editor"), (GENERAL_ID, "general-purpose")]:
        (subs / f"agent-{aid}.jsonl").write_text(
            line(parentUuid=None, type="user", uuid=f"u{aid}", agentId=aid))
        (subs / f"agent-{aid}.meta.json").write_text(json.dumps({"agentType": kind}))
    return main


def record(main: Path, who: str) -> Path:
    """The record of `who`: the coordinator's and the session's in the
    session directory, a subagent's in the directory of the sessions."""
    where = main.with_suffix("") if who in ("main", "session") else main.parent
    return where / "reader-commits" / who


def both(commit: str) -> str:
    return f"{commit}\n{commit}\n"


def call(main: Path, tool: str, inp: dict[str, Any],
         agent: str | None = None) -> dict[str, Any]:
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": inp,
            "tool_use_id": "t1", "transcript_path": str(main),
            "cwd": str(checkout.ROOT), **({"agent_id": agent} if agent else {})}


def session_start(main: Path) -> None:
    run(command("SessionStart"), {"hook_event_name": "SessionStart", "source": "compact",
                                  "transcript_path": str(main), "cwd": str(checkout.ROOT)})


def test_coordinator_gets_the_diff_once(tmp_path: Path) -> None:
    main = session(tmp_path)
    bash = command("PreToolUse", "Bash|Monitor")
    session_start(main)
    assert record(main, "main").read_text() == both(head())
    assert record(main, "session").read_text() == f"{head()}\n"
    record(main, "main").write_text(both(BEFORE))
    session_start(main)
    assert record(main, "main").read_text() == both(BEFORE)
    out = json.loads(run(bash, call(main, "Bash", {"command": "ls"})))
    text = out["hookSpecificOutput"]["additionalContext"]
    assert f"context --update {BEFORE} {BEFORE} coordinator`" in text
    assert record(main, "main").read_text() == both(head())
    assert run(bash, call(main, "Bash", {"command": "ls"})) == ""


def test_subagents(tmp_path: Path) -> None:
    main = session(tmp_path)
    session_start(main)
    start = command("SubagentStart")
    for aid in (EDITOR_ID, GENERAL_ID):
        run(start, {"hook_event_name": "SubagentStart", "agent_id": aid,
                    "transcript_path": str(main), "cwd": str(checkout.ROOT)})
        assert record(main, aid).read_text().split()[1] == head()
        record(main, aid).write_text(both(BEFORE))
    run(start, {"hook_event_name": "SubagentStart", "agent_id": EDITOR_ID,
                "transcript_path": str(main), "cwd": str(checkout.ROOT)})
    assert record(main, EDITOR_ID).read_text() == both(BEFORE)
    denied = call(main, "Bash", {"command": "ls", "timeout": 600000}, EDITOR_ID)
    out = json.loads(run(command("PreToolUse", "Bash|Monitor"), denied))["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "context agent code-editor" in out["additionalContext"]
    assert record(main, EDITOR_ID).read_text() == both(head())
    agent = command("PreToolUse", "Agent")
    assert run(agent, call(main, "Agent", {"subagent_type": "code-editor"}, EDITOR_ID)) == ""
    assert run(agent, call(main, "Agent", {"subagent_type": "code-editor"}, GENERAL_ID)) == ""
    assert record(main, GENERAL_ID).read_text() == both(head())
