"""The split of a transcript's wall time into parts, which a misread entry
shifts without any failure, and the agents pending to a run, which a hook
reads to deny a wait and which a misread entry drops without any failure."""

import json
from pathlib import Path

import pytest

from tests.conftest import script

profile_runs = script("profile_runs")
Part = profile_runs.Part


def at(s: float) -> str:
    return f"2026-10-04T00:{int(s) // 60:02d}:{int(s) % 60:02d}.000Z"


def assistant(s: float, *blocks: dict, stop: str | None = None) -> dict:
    return {"type": "assistant", "timestamp": at(s),
            "message": {"content": list(blocks), "stop_reason": stop}}


def user(s: float, content, result: dict | None = None, **extra) -> dict:
    e = {"type": "user", "timestamp": at(s), "message": {"content": content}, **extra}
    if result is not None:
        e["toolUseResult"] = result
    return e


def bash(tid: str, command: str, **inp) -> dict:
    return {"type": "tool_use", "id": tid, "name": "Bash",
            "input": {"command": command, **inp}}


def answer(tid: str) -> list[dict]:
    return [{"type": "tool_result", "tool_use_id": tid, "content": "ok"}]


NOTE = ("<task-notification>\n<task-id>b1</task-id>\n<tool-use-id>t2</tool-use-id>\n"
        "<status>completed</status>\n</task-notification>")


@pytest.fixture
def run(tmp_path: Path):
    entries = [
        user(0, "brief"),
        assistant(5, bash("t1", "G=scripts/gate.py; uptime; time uv run python $G out")),
        user(15, answer("t1")),
        assistant(20, bash("t2", "uv run python scripts/run_dl.py sweep a1b2c3d4",
                           run_in_background=True)),
        user(21, answer("t2"), {"backgroundTaskId": "b1"}),
        assistant(23, {"type": "text", "text": "waiting"}, stop="end_turn"),
        user(123, NOTE, isMeta=True),
        assistant(125, bash("t3", "until [ -f x ]; do sleep 5; done")),
        user(145, answer("t3")),
        assistant(150, {"type": "tool_use", "id": "t4", "name": "SubagentHandback",
                        "input": {"message": "done"}}),
        user(151, answer("t4"), {"success": True}, toolEndsTurn=True),
        user(160, "<local-command-stdout>Compacted</local-command-stdout>"),
        user(200, "a question"),
        assistant(210, {"type": "text", "text": "an answer"}, stop="end_turn"),
    ]
    path = tmp_path / "s.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    return profile_runs.profile(path, [])


def test_parts(run) -> None:
    assert run.wall == 210
    assert run.parts == {Part.MODEL: 5 + 5 + 2 + 2 + 5 + 10, Part.TOOLS: 10 + 1,
                         Part.WAITS: 1 + 100 + 20, Part.IDLE: 49}


def test_labels(run) -> None:
    assert run.groups[(Part.TOOLS, "gate")].time == 10
    sweep = run.groups[(Part.WAITS, "bg run_dl.py sweep")]
    assert (sweep.time, sweep.ran) == (101, 102)
    assert run.groups[(Part.WAITS, "poll")].time == 20


def agent_call(tid: str, background: bool = True) -> dict:
    return {"type": "tool_use", "id": tid, "name": "Agent",
            "input": {"description": tid, "subagent_type": "editor",
                      "run_in_background": background}}


def send(tid: str, to: str) -> dict:
    return {"type": "tool_use", "id": tid, "name": "SendMessage",
            "input": {"to": to, "message": "more"}}


def told(aid: str, tid: str, note: str = "") -> str:
    return (f"<task-notification>\n<task-id>{aid}</task-id>\n<tool-use-id>{tid}"
            f"</tool-use-id>\n<status>completed</status>\n{note}</task-notification>")


A1, A2, A3, A4 = (f"a{n:016x}" for n in (1, 2, 3, 4))


def test_pending(tmp_path: Path) -> None:
    """An agent is pending from its launch, or from a SendMessage call that
    resumed it, to its report. A notification that it stopped with work of
    its own running is a report, and so is a later notification in another
    transcript of the session, and a message queued to it resumes none."""
    entries = [
        user(0, "brief"),
        assistant(1, agent_call("c1"), agent_call("c2")),
        user(2, answer("c1"), {"status": "async_launched", "agentId": A1}),
        user(2, answer("c2"), {"status": "async_launched", "agentId": A2}),
        assistant(3, agent_call("c3", background=False)),
        user(20, answer("c3"), {"status": "completed", "agentId": A3}),
        user(30, told(A1, "c1"), isMeta=True),
        assistant(40, send("s1", A1)),
        user(41, answer("s1"), {"success": True, "message": "Resuming agent a000000",
                                "pin": {"id": A1}}),
        user(50, told(A2, "c2", "<note>This agent stopped with background work of "
                      "its own still running.</note>"), isMeta=True),
        assistant(55, send("s2", A2)),
        user(56, answer("s2"), {"success": True, "pin": {"id": A2},
                                "message": f"Message queued for delivery to {A2}"}),
        assistant(60, agent_call("c4")),
        user(61, answer("c4"), {"status": "async_launched", "agentId": A4}),
        assistant(70, send("s3", A3)),
        user(71, answer("s3"), {"success": True, "message": "Resuming agent a000000",
                                "resumedAgentId": A3, "pin": {"id": A3}}),
    ]
    path = tmp_path / "s.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    agents = tmp_path / "s" / "subagents"
    agents.mkdir(parents=True)
    elsewhere = [user(35, told(A1, "x1"), isMeta=True),
                 user(80, told(A3, "x3"), isMeta=True)]
    for aid, tid in ((A1, "c1"), (A2, "c2"), (A3, "c3")):
        (agents / f"agent-{aid}.jsonl").write_text("")
        (agents / f"agent-{aid}.meta.json").write_text(json.dumps(
            {"agentType": "editor", "toolUseId": tid}))
    assert profile_runs.pending_agents(path, []) == [A1, A3, A4]
    (agents / f"agent-{A2}.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in elsewhere))
    assert profile_runs.pending_agents(path, []) == [A1, A4]
