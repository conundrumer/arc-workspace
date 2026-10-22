"""The launches of a run (`agent_launches.launches`), each held across the
growth of its transcript, which a launch held past a change to what it is
made from gives stale with no failure."""

import json
import sys
from pathlib import Path

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
agent_launches = script("agent_launches")
transcripts = sys.modules["transcripts"]


def add(path: Path, *entries: dict) -> None:
    with path.open("a") as fh:
        fh.write("".join(json.dumps(e) + "\n" for e in entries))


def at(s: int) -> str:
    return f"2026-10-04T00:00:{s:02d}.000Z"


def call(tid: str, s: int) -> dict:
    return {"type": "assistant", "timestamp": at(s), "message": {"content": [
        {"type": "tool_use", "id": tid, "name": "Agent",
         "input": {"description": "d", "prompt": "p", "subagent_type": "worker",
                   "run_in_background": True}}]}}


def result(tid: str, s: int, status: str, agent: str) -> dict:
    return {"type": "user", "timestamp": at(s), "toolUseResult": {"status": status, "agentId": agent},
            "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": "ok"}]}}


def told(tid: str, agent: str, s: int) -> dict:
    note = (f"<task-notification>\n<task-id>{agent}</task-id>\n<tool-use-id>{tid}</tool-use-id>\n"
            "<status>completed</status>\n</task-notification>")
    return {"type": "user", "timestamp": at(s), "isMeta": True, "message": {"content": note}}


def read(path: Path) -> tuple[list[tuple[str | None, bool]], list[str]]:
    transcripts.new_state()
    undecided: list[str] = []
    return [(a.agent, a.pending) for a in agent_launches.launches(path, undecided)], undecided


def test_launches_kept(tmp_path: Path) -> None:
    """A launch held from an earlier read gives what a read of the whole
    transcript gives once a notification of it comes, and the `undecided`
    lines its making gave at each read."""
    path = tmp_path / "s.jsonl"
    add(path, {"type": "user", "timestamp": at(0), "message": {"content": "brief"}},
        call("t1", 1), result("t1", 2, "async_launched", "a1"),
        call("t2", 3), result("t2", 4, "odd", "a2"))
    first = read(path)
    assert first[0] == [("a1", True), ("a2", False)] and first[1]
    assert read(path) == first
    add(path, told("t1", "a1", 5))
    launches, lines = read(path)
    assert launches == [("a1", False), ("a2", False)]
    whole = tmp_path / "whole.jsonl"
    whole.write_bytes(path.read_bytes())
    assert read(whole) == (launches, lines)


def test_reports_received_elsewhere(tmp_path: Path) -> None:
    """A cached launch sees a delivery at another receiver; a later resume
    still needs a later report, and quoted or unrelated reports do not count."""
    path = tmp_path / "s.jsonl"
    agents = tmp_path / "s" / "subagents"
    agents.mkdir(parents=True)
    child = agents / "agent-a1.jsonl"
    child.write_text("")
    child.with_suffix(".meta.json").write_text(json.dumps({"toolUseId": "t1"}))
    receiver = agents / "agent-a2.jsonl"
    add(path, call("t1", 1), result("t1", 2, "async_launched", "a1"))
    add(receiver, {"type": "user", "timestamp": at(3), "message": {"content": "brief"}})
    assert read(path)[0] == [("a1", True)]

    def message(agent: str, s: int, text: str) -> dict:
        return {"type": "user", "timestamp": at(s), "message": {"content":
                f'<agent-message from="{agent}">{text}</agent-message>'}}

    text = "[Subagent hand-back] The report follows:\n  finished"
    add(receiver, message("a3", 4, text), {"type": "user", "timestamp": at(5),
        "message": {"content": [{"type": "tool_result", "tool_use_id": "quoted",
                                  "content": message("a1", 5, text)["message"]["content"]}]}})
    assert read(path)[0] == [("a1", True)]
    add(receiver, message("a1", 6, text))
    assert read(path)[0] == [("a1", False)]
    reports = sys.modules["agent_reports"]
    launch = agent_launches.launches(path, [])[0]
    assert [r.text for r in launch.reports(0, [])] == ["finished"]
    assert [r.text for r in reports.reports(child, 0, [])] == ["finished"]
    add(receiver, {"type": "assistant", "timestamp": at(7), "message": {"content": [
        {"type": "tool_use", "id": "resume", "name": "SendMessage",
         "input": {"to": "a1", "message": "continue"}}]}},
        {"type": "user", "timestamp": at(7), "toolUseResult": {"resumedAgentId": "a1"},
         "message": {"content": [{"type": "tool_result", "tool_use_id": "resume",
                                   "content": "resumed"}]}})
    transcripts.new_state()
    resumed = agent_launches.launched(path, [])[0]
    assert resumed.pending and resumed.reports(resumed.since, []) == []
    notification = told("t1", "a1", 8)
    notification["message"]["content"] = notification["message"]["content"].replace(
        "</task-notification>", "<result>later</result>\n</task-notification>")
    add(receiver, {"type": "queue-operation", "operation": "enqueue", "timestamp": at(8),
                   "content": notification["message"]["content"]})
    assert read(path)[0] == [("a1", False)]
    transcripts.new_state()
    assert not agent_launches.launched(path, [])[0].pending
    assert [r.text for r in reports.reports(child, 0, [])] == ["finished", "later"]
    latest = agent_launches.launched(path, [])[0]
    assert [r.text for r in latest.reports(latest.since, [])] == ["later"]
    assert latest.done is not None
    assert reports.reports(child, latest.done, []) == []
