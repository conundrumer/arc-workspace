"""The split of a transcript's wall time into parts, which a misread entry
shifts without any failure."""

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
