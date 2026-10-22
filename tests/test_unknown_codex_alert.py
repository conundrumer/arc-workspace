"""A Codex attempt held because whether its turn runs is unknown reaches the
coordinator once per quiet stretch of `STUCK_SECONDS` over the writes to its
transcripts and its Codex rollout, and stays held."""

import json
import os
import shlex
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_quiet_ended_turn import (EDITOR, ME, agent_launches, agent_turns, handback,
                                         open_agents, operator_state, resumed, run_profiler,
                                         state_reads, text_end, transcripts)

NOW = 2_000_000_000.0


def unknown_read(scratch: Path | None, rollout: Path | None, limits: tuple[str, ...] = ()):
    return operator_state.CodexRead(operator_state.CodexEnd.UNKNOWN, "daemon down", scratch,
                                    rollout, limits)


def held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, read, *, transcript_age: float,
         rollout_age: float | None):
    """`ends_read` of a Codex attempt whose launcher ended, whose Codex state
    `read` gives, its transcript last written `transcript_age` seconds before
    `NOW` and its rollout `rollout_age` seconds before, where that is given."""
    from operations.roles import Role
    from operations.state import Agent, Report, Running, Waits
    monkeypatch.setattr(transcripts, "project_dirs", lambda: [tmp_path])
    path = tmp_path / "p" / "s" / "subagents" / f"agent-{EDITOR}.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in [
        *handback("2026-10-18T23:35:58.581Z"), resumed("2026-10-18T23:44:23.958Z"),
        text_end("2026-10-18T23:44:27.267Z")]))
    path.with_suffix(".meta.json").write_text(json.dumps({"agentType": "doc-editor",
                                                          "description": "x"}))
    os.utime(path, (NOW - transcript_age, NOW - transcript_age))
    if rollout_age is not None and read.rollout is not None:
        read.rollout.write_text("{}\n")
        os.utime(read.rollout, (NOW - rollout_age, NOW - rollout_age))
    monkeypatch.setattr(operator_state, "codex_end", lambda *_: read)
    state_reads.new_state()
    launch = agent_launches.Launch(EDITOR, path, NOW - 3000, None, "c1", ())
    listing = [open_agents.Listed(ME, path, launch, run_profiler.profile(path, []),
                                  agent_turns.has_ended(path), None, None)]
    report_file = tmp_path / "reply.txt"
    report_file.write_text("report")
    a = Agent(EDITOR, ME, Role.DOC_EDITOR, "11-1683", "brief", NOW - 4000, NOW - 3000,
              Running(Waits.STILL_RUNNING), (Report(NOW - 3500, "done"),), True, report_file)
    out = operator_state.ends_read([a], ME, listing, [], NOW, [], closes={})
    return out, operator_state.stuck_read("s", out.quiet, [], {}, out.unknown)


def test_the_attempt_stays_held_and_is_stuck_once_quiet_for_the_bound(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from operations.constants import STUCK_SECONDS
    scratch = tmp_path / "scratch dir"
    rollout = tmp_path / "rollout.jsonl"
    read, stuck = held(tmp_path, monkeypatch, unknown_read(scratch, rollout),
                       transcript_age=STUCK_SECONDS, rollout_age=STUCK_SECONDS + 50)
    assert EDITOR in read.held
    assert read.agents[0].pending
    assert stuck[EDITOR].since == NOW - STUCK_SECONDS
    diagnostic = stuck[EDITOR].unknown
    assert diagnostic is not None
    assert f"codex_agent.py show {shlex.quote(str(scratch))}" in diagnostic


def test_a_write_to_the_rollout_inside_the_bound_prevents_the_alert(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from operations.constants import STUCK_SECONDS
    rollout = tmp_path / "rollout.jsonl"
    read, stuck = held(tmp_path, monkeypatch, unknown_read(tmp_path, rollout),
                       transcript_age=STUCK_SECONDS * 3, rollout_age=STUCK_SECONDS - 1)
    assert EDITOR in read.held and stuck == {}


def test_a_transcript_write_inside_the_bound_prevents_the_alert(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from operations.constants import STUCK_SECONDS
    read, stuck = held(tmp_path, monkeypatch, unknown_read(tmp_path, None),
                       transcript_age=STUCK_SECONDS - 1, rollout_age=None)
    assert EDITOR in read.held and stuck == {}


def test_an_unrecovered_scratch_path_is_stated_with_no_command(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from operations.constants import STUCK_SECONDS
    _, stuck = held(tmp_path, monkeypatch, unknown_read(None, None),
                    transcript_age=STUCK_SECONDS, rollout_age=None)
    diagnostic = stuck[EDITOR].unknown
    assert diagnostic is not None
    assert "codex_agent.py" not in diagnostic
    assert "its scratch path is not recovered" in diagnostic


def test_an_unreadable_rollout_is_named_and_the_launch_time_bounds_the_stretch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from operations.constants import STUCK_SECONDS
    missing = tmp_path / "gone.jsonl"
    _, stuck = held(tmp_path, monkeypatch, unknown_read(tmp_path, missing),
                    transcript_age=STUCK_SECONDS * 4, rollout_age=None)
    assert stuck[EDITOR].since == NOW - 3000
    assert f"{missing} does not exist" in (stuck[EDITOR].unknown or "")


def test_the_message_goes_once_per_stretch_and_a_later_write_allows_a_new_one(
        tmp_path: Path) -> None:
    from operations import alerts
    from operations.constants import COORDINATOR
    from operations.journal import Journal
    from operations.state import Stuck
    from operations.steps import Send, key
    from tests.test_idle_changes import entry, idle_state
    st, t = idle_state(tmp_path)
    s = Stuck("s", st.now - 1000, (), "whether a Codex turn runs for it is unknown (daemon down)")
    st = replace(st, transcripts=replace(st.transcripts, stuck={EDITOR: s}))
    first = alerts.stuck(st)
    assert isinstance(first, Send) and first.to == COORDINATOR
    assert "unknown (daemon down)" in first.message
    done = entry(COORDINATOR, first.message, None, st.now - 100, key(first))
    again = alerts.stuck(replace(st, journal=Journal((done,))))
    assert not isinstance(again, Send)
    later = replace(s, since=st.now - 500)
    renewed = alerts.stuck(replace(st, journal=Journal((done,)), transcripts=replace(
        st.transcripts, stuck={EDITOR: later})))
    assert isinstance(renewed, Send) and renewed != first
