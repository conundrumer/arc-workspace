"""A launcher must pass received agent messages to Codex before it ends."""

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
relay = script("codex_relay_hook")
state = script("state_reads")
entry = script("hook_entry")
joined = script("joined_hooks")

AGENT = "a0000000000000001"
SENDER = "a0000000000000002"


def launch(tmp_path: Path, at: int, resume: bool = False) -> dict[str, Any]:
    command = (f"uv run python scripts/codex_agent.py code-editor {tmp_path / 'codex'} "
               f"{tmp_path / 'brief'} model high" + (" --resume" if resume else ""))
    return {"type": "assistant", "uuid": f"launch-{at}",
            "timestamp": f"2026-10-23T19:00:{at:02d}Z", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "id": f"call-{at}",
                 "input": {"command": command}}]}}


def message(at: int, text: str = "Review the fixes.", sender: str = SENDER) -> dict[str, Any]:
    return {"type": "user", "uuid": f"message-{at}",
            "timestamp": f"2026-10-23T19:00:{at:02d}Z", "message": {"content":
                f'<agent-message from="{sender}">{text}</agent-message>'}}


def session(tmp_path: Path, entries: list[dict[str, Any]],
            tool: str | None) -> tuple[Path, dict[str, Any]]:
    path = tmp_path / "s" / "subagents" / f"agent-{AGENT}.jsonl"
    path.parent.mkdir(parents=True)
    path.with_suffix(".meta.json").write_text(json.dumps({"agentType": "codex-launcher"}))
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    hook: dict[str, Any] = {"agent_id": AGENT, "transcript_path": str(tmp_path / "s.jsonl")}
    if tool is not None:
        hook["tool_name"] = tool
    return path, hook


@pytest.mark.parametrize("tool", [None, "SubagentHandback"])
def test_unpassed_message_blocks_once_and_new_message_blocks_again(tmp_path: Path, tool):
    path, hook = session(tmp_path, [launch(tmp_path, 1), message(2)], tool)
    assert relay.check(hook) is not None
    assert relay.check(hook) is None
    with path.open("a") as stream:
        stream.write(json.dumps(message(3)) + "\n")
    state.new_state()
    assert relay.check(hook) is not None
    assert relay.check(hook) is None


@pytest.mark.parametrize("tool", [None, "SubagentHandback"])
@pytest.mark.parametrize("entries", ["resumed", "handback", "earlier", "same-time"])
def test_messages_that_need_no_delivery_pass(tmp_path: Path, tool, entries):
    lines = [launch(tmp_path, 1), message(2)]
    if entries == "resumed":
        lines.append(launch(tmp_path, 3, resume=True))
    elif entries == "handback":
        lines[-1] = message(2, "[Subagent hand-back] Done. The report follows:\n  Fixed.")
    elif entries == "earlier":
        lines = [message(1), launch(tmp_path, 2)]
    elif entries == "same-time":
        lines[-1] = message(1)
    _, hook = session(tmp_path, lines, tool)
    assert relay.check(hook) is None


def test_stop_and_handback_share_the_denial_record(tmp_path: Path):
    _, hook = session(tmp_path, [launch(tmp_path, 1), message(2)], None)
    assert relay.check(hook) is not None
    assert relay.check(hook | {"tool_name": "SubagentHandback"}) is None


def test_other_tools_are_not_registered():
    with pytest.raises(ValueError):
        relay.check({"tool_name": "Bash"})


def test_joined_stop_blocks_for_an_unpassed_message(tmp_path: Path, monkeypatch, capsys):
    _, hook = session(tmp_path, [launch(tmp_path, 1), message(2)], None)
    monkeypatch.setattr(sys, "argv", ["joined_hooks.py", "stop"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook)))
    assert joined.main() == 0
    out = capsys.readouterr()
    assert json.loads(out.out)["decision"] == "block"
    assert "cannot read" not in out.err


def test_stop_reports_all_checks_even_when_one_fails(monkeypatch, capsys):
    def deny(hook):
        return hook["reason"]

    def fail(hook):
        raise ValueError("check failed")

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"reason": "blocked"})))
    assert entry.run_subagent_stop("test", [deny, fail, deny]) == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == {"decision": "block", "reason": "blocked\nblocked"}
    assert "ValueError" in out.err
