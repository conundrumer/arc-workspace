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
