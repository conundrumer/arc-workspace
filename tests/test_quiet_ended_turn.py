"""A quiet pending agent ends where its record gives a stop after its last
resume and its own work is not running, and no stuck alert names it; where
it gave no stop, or its work is running, it stays stuck."""

import json
import os
import sys
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
operator_state = script("operator_state")
transcripts = sys.modules["transcripts"]
open_agents = sys.modules["open_agents"]
agent_turns = sys.modules["agent_turns"]
agent_launches = sys.modules["agent_launches"]
run_profiler = sys.modules["run_profiler"]
state_reads = sys.modules["state_reads"]

ME, EDITOR, SENDER = "a00000000000000f1", "a0000000000000a12", "a0000000000000a35"


def handback(t: str) -> list[dict]:
    return [{"type": "assistant", "timestamp": t,
             "message": {"content": [{"type": "tool_use", "id": "t1",
                                      "name": "SubagentHandback", "input": {}}],
                         "stop_reason": "tool_use"}},
            {"type": "user", "timestamp": t, "toolEndsTurn": True,
             "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                      "content": "Report delivered to your caller."}]}}]


def resumed(t: str) -> dict:
    return {"type": "user", "timestamp": t,
            "message": {"content": "Another Claude session sent a message while you were "
                                   f'working: <agent-message from="{SENDER}">'}}


def text_end(t: str) -> dict:
    return {"type": "assistant", "timestamp": t,
            "message": {"content": [{"type": "text", "text": "Done."}],
                        "stop_reason": "end_turn"}}


def in_turn(t: str) -> dict:
    return {"type": "assistant", "timestamp": t,
            "message": {"content": [{"type": "tool_use", "id": "t2", "name": "Bash",
                                     "input": {"command": "true"}}],
                        "stop_reason": "tool_use"}}


def ends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, last: dict,
         *, still_running: bool = False, live_work: bool = False):
    """`ends_read` of the doc editor of change 11-1683 as session
    2384db39 read it: a resume by another agent's message after its report
    was delivered, then `last`, whose stop the record of its attempt gives
    where `last` ends its turn, read past `STUCK_SECONDS`."""
    from operations import attempts as events
    from operations.constants import STUCK_SECONDS
    from operations.roles import Described, Role
    from operations.state import Agent, Report, Running, Waits
    monkeypatch.setattr(transcripts, "project_dirs", lambda: [tmp_path])
    path = tmp_path / "p" / "s" / "subagents" / f"agent-{EDITOR}.jsonl"
    path.parent.mkdir(parents=True)
    entries = [*handback("2026-10-18T23:35:58.581Z"), resumed("2026-10-18T23:44:23.958Z"), last]
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    path.with_suffix(".meta.json").write_text(json.dumps({"agentType": "doc-editor",
                                                          "description": "x"}))
    state_reads.new_state()
    since = agent_turns.last_time(path)
    os.utime(path, (since, since))
    state_reads.new_state()
    launch = agent_launches.Launch(EDITOR, path, since, None, "c1", ())
    listing = [open_agents.Listed(ME, path, launch, run_profiler.profile(path, []),
                                  agent_turns.has_ended(path), None, None)]
    if live_work:
        listing[0].running = [sys.modules["run_records"].Span("Bash", "codex", since, "task")]
    record = [events.Launched(source="launch", at=since - 700, agent=EDITOR,
                              seat=Described(Role.DOC_EDITOR, "11-1683"), parent=ME,
                              agent_type="doc-editor", transport=events.Transport.CLAUDE),
              events.HandedBack(source="handback", at=since - 600, agent=EDITOR, text="done"),
              events.Resumed(source="resume", at=since - 4, agent=EDITOR, parent=SENDER)]
    if last["message"]["stop_reason"] == "end_turn":
        record.append(events.Stopped(source="stop", at=since, agent=EDITOR, text="Done."))
    script("attempt_record").Record().append(*record)
    report_file = tmp_path / "reply.txt"
    report_file.write_text("completed role report")
    agent = Agent(EDITOR, ME, Role.DOC_EDITOR, "11-1683", "brief", since - 600, since - 4,
                  Running(Waits.STILL_RUNNING if still_running else Waits.AT_WORK),
                  (Report(since - 600, "done"),), True, report_file)
    read = operator_state.ends_read([agent], listing, [], since + STUCK_SECONDS + 1, [], closes={})
    return read, operator_state.stuck_read("s", read.quiet, [], {})


def test_a_quiet_agent_whose_turn_is_in_progress_stays_stuck(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    read, stuck = ends(tmp_path, monkeypatch, in_turn("2026-10-18T23:44:27.267Z"))
    assert EDITOR in stuck
    assert read.agents[0].waits is not None


@pytest.mark.parametrize("live_work", [True, False])
def test_a_yielded_quiet_agent_ends_only_once_its_work_ends(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, live_work: bool) -> None:
    read, stuck = ends(tmp_path, monkeypatch, text_end("2026-10-18T23:44:27.267Z"),
                       still_running=True, live_work=live_work)
    assert read.agents[0].pending is live_work
    assert (EDITOR in read.ended) is not live_work
    assert (EDITOR in stuck) is live_work
