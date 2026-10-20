"""The split of a transcript's wall time into parts, which a misread entry
shifts without any failure, the agents pending to a run, which a hook
reads to deny a wait and which a misread entry drops without any failure,
and the runs `--under` takes, which a misread call drops without any
failure.
The hook allows a call where its check fails, so a check that fails on its
own error is silent too."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from engine import checkout
from tests.conftest import script

profile_runs = script("profile_runs")
under_runs = sys.modules["under_runs"]
transcripts = sys.modules["transcripts"]
transcript_entries = sys.modules["transcript_entries"]
tree_reads = sys.modules["tree_reads"]
Part = sys.modules["run_records"].Part


def write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


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


def entries() -> list[dict]:
    return [
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


@pytest.fixture
def run(tmp_path: Path):
    path = tmp_path / "s.jsonl"
    write_jsonl(path, entries())
    return profile_runs.profile(path, [])


def test_parts(run) -> None:
    assert run.wall == 210
    assert run.parts == {Part.MODEL: 5 + 5 + 2 + 2 + 5 + 10, Part.TOOLS: 10 + 1,
                         Part.WAITS: 1 + 100 + 20, Part.IDLE: 49}


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


A1, A2, A3, A4, A5 = (f"a{n:016x}" for n in (1, 2, 3, 4, 5))


def test_kept_profile(tmp_path: Path) -> None:
    """The profile a fold keeps across a transcript's growth and rewrite is
    the profile of the whole transcript, also where the end of a call in
    the background, which its output file gives, falls in an idle gap the
    fold passed before that end was known."""
    out = tmp_path / "out.txt"
    out.write_text("")
    ended = transcript_entries.epoch(at(60))
    os.utime(out, (ended, ended))
    lines = entries()
    lines[5:5] = [assistant(21, bash("t5", "sleep 1000", run_in_background=True)),
                  user(22, [{"type": "tool_result", "tool_use_id": "t5",
                               "content": f"Output is being written to: {out}"}],
                       {"backgroundTaskId": "b5"})]
    path = tmp_path / "s.jsonl"
    path.write_text("")

    def same_as_whole(n: int) -> None:
        whole = tmp_path / f"{n}.jsonl"
        whole.write_bytes(path.read_bytes())
        transcripts.new_state()
        kept = profile_runs.profile(path, [])
        assert kept == replace(profile_runs.profile(whole, []), label=kept.label, path=path), n

    for n, e in enumerate(lines):
        with path.open("a") as fh:
            fh.write(json.dumps(e) + "\n")
        same_as_whole(n)
    write_jsonl(path, [user(0, "another brief"), *lines[1:]])
    same_as_whole(len(lines))
    groups = profile_runs.profile(path, []).groups
    assert groups[Part.WAITS, "bg poll"].ran == 60 - 22
    assert groups[Part.WAITS, "bg poll"].time == 22 - 21 + (60 - 23) / 2


def test_pending(tmp_path: Path) -> None:
    """An agent is pending from its launch, or from a SendMessage call that
    resumed it, by the run or by another agent of the session, to its
    report. A notification that it stopped with work of its own running is
    a report, and so is a later notification in another transcript of the
    session, and a message queued to it resumes none."""
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
    write_jsonl(path, entries)
    agents = tmp_path / "s" / "subagents"
    agents.mkdir(parents=True)
    elsewhere = [user(35, told(A1, "x1"), isMeta=True),
                 user(80, told(A3, "x3"), isMeta=True)]
    for aid, tid in ((A1, "c1"), (A2, "c2"), (A3, "c3")):
        (agents / f"agent-{aid}.jsonl").write_text("")
        (agents / f"agent-{aid}.meta.json").write_text(json.dumps(
            {"agentType": "editor", "toolUseId": tid}))
    assert profile_runs.pending_agents(path, []) == [A1, A3, A4]
    write_jsonl(agents / f"agent-{A2}.jsonl", elsewhere)
    transcripts.new_state()
    assert profile_runs.pending_agents(path, []) == [A1, A4]
    resumer = [assistant(90, send("r1", "editor")),
               user(91, answer("r1"), {"success": True, "message": "Resuming agent a000000",
                                       "pin": {"id": A2}})]
    write_jsonl(agents / f"agent-{A5}.jsonl", resumer)
    transcripts.new_state()
    assert profile_runs.pending_agents(path, []) == [A1, A2, A4]


def test_hook_denies(tmp_path: Path) -> None:
    """The wait hook, run in a fresh process as the settings register it,
    denies a `sleep` that names an agent pending to the caller."""
    wait = bash("w1", f"sleep 30; ls /tmp/{A1}")
    entries = [
        user(0, "brief"),
        assistant(1, agent_call("c1")),
        user(2, answer("c1"), {"status": "async_launched", "agentId": A1}),
        assistant(3, wait),
    ]
    path = tmp_path / "s.jsonl"
    write_jsonl(path, entries)
    settings = json.loads((checkout.claude() / "settings.json").read_text())
    [command] = [h["command"] for m in settings["hooks"]["PreToolUse"]
                 if m.get("matcher") == "Bash|Monitor" for h in m["hooks"]]
    hook = {"tool_name": "Bash", "tool_input": wait["input"],
            "tool_use_id": "w1", "transcript_path": str(path)}
    done = subprocess.run(command, shell=True, input=json.dumps(hook),
                          capture_output=True, text=True, check=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(checkout.ROOT)})
    assert done.stdout, done.stderr
    decision = json.loads(done.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny", done.stderr


def test_under(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--under` takes the runs under the run, the agents its agents
    launched among them, whose work is not open and that ran after an
    operator's previous call of it that completed in the foreground with no
    error, or that call's `left open:` line gives; a call by an agent of
    another type, one that failed, one the harness moved to the background
    and one whose output was cut before that line count as none."""
    op, c1, c2, g, editor, other, busy, late = (f"a{n:016x}" for n in range(1, 9))
    agents = tmp_path / "proj" / "s" / "subagents"
    agents.mkdir(parents=True)
    out = f"left open: {late}\nruns taken: 0\nprevious call: none\n"

    def call(tid: str, s: float, result: dict, error: bool = False) -> list[dict]:
        done = [{"type": "tool_result", "tool_use_id": tid, "content": result.get("content", out),
                 "is_error": error}]
        return [assistant(s, bash(tid, f"cd x && uv run python scripts/profile_runs.py "
                                       f"--under agent-{op} 2>&1")),
                user(s + 1, done, result)]

    def said(s: float) -> dict:
        return assistant(s, {"type": "text", "text": "a"})

    cut = {"content": "<persisted-output>\nOutput too large (35.3KB).",
           "stdout": f"left open: {late}\nruns taken: 1 {late}", "stderr": ""}
    runs = {op: ("operator", None, [user(0, "brief"), *call("u1", 30, {})]),
            c1: ("editor", op, [user(1, "brief"), said(10)]),
            c2: ("editor", op, [user(2, "brief"), said(35)]),
            g: ("editor", c1, [user(3, "brief"), said(60)]),
            busy: ("editor", op, [user(4, "brief"), said(70)]),
            late: ("editor", op, [user(5, "brief"), said(20)]),
            editor: ("code-editor", None, [user(0, "brief"), *call("u2", 40, {})]),
            other: ("operator", None, [user(0, "brief"), *call("u3", 45, {}, error=True),
                                       *call("u4", 47, {"backgroundTaskId": "b",
                                                        "assistantAutoBackgrounded": True}),
                                       *call("u5", 50, cut)])}
    for aid, (kind, parent, entries) in runs.items():
        write_jsonl(agents / f"agent-{aid}.jsonl", entries)
        (agents / f"agent-{aid}.meta.json").write_text(json.dumps(
            {"agentType": kind, **({"parentAgentId": parent} if parent else {})}))
    monkeypatch.setattr(transcripts, "project_dirs", lambda: [tmp_path])
    monkeypatch.setattr(tree_reads, "scratch", lambda session: tmp_path / "none")
    monkeypatch.setattr(under_runs, "work_open",
                        lambda p, undecided: transcripts.agent_id(p) == busy)
    transcripts.new_state()
    try:
        taken = under_runs.runs_since(agents / f"agent-{op}.jsonl", op, [])
        previous = under_runs.previous_call(agents / f"agent-{op}.jsonl", op, [])
    finally:
        transcripts.new_state()
    assert previous == under_runs.Previous(transcript_entries.epoch(at(30)), op,
                                             frozenset([late]))
    assert sorted(transcripts.agent_id(p) for p in taken) == sorted([c2, g, late])
