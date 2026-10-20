"""Merged changes finish their closing sequence without another take."""

import shlex
from dataclasses import replace
from pathlib import Path

import pytest

from tests.conftest import script
from tests.test_ticket_stall import FILED, ME, TAKEN, state

OTHER = "a00000000000000f2"
HASH = "47fdd338" + "0" * 32
NAME = "9-1_change_x_ticket-analyst.md"


def merged_state(tmp_path: Path, source: str, status: str = "released"):
    from operations.merging import merge_command
    from operations.state import Call, Commit, Merge, Message, Tool

    w = tmp_path / ".claude" / "worktrees" / "change-9-1"
    lines = (TAKEN + f"{FILED} assigned [operator {ME}]: worktree {w}\n"
             + f"{FILED} {status} [coordinator]: merged {HASH[:8]}\n")
    s = state(tmp_path, {f"{status}/{NAME}": lines}, budgets=["9-1"])
    t = s.tracker.tickets["9-1"]
    at = t.last_time + 10
    commit = Commit(HASH, at, frozenset(),
                    t.title if source == "commit" else "coordinator's commit", False, frozenset())
    calls = ()
    messages = ()
    if source in ("result", "pending"):
        calls = (Call(ME, at, Tool.BASH, {"command": merge_command(t, w)},
                      "merged" if source == "result" else None, False,
                      Merge.MERGED if source == "result" else None),)
    if source == "directive":
        # A line recorded for an earlier operator must also stop this one
        # from taking the change, without relying on transcript handover.
        messages = (Message(OTHER, at, None, "Op merged: 9-1.", stored=True),)
    return replace(s, operators=(OTHER, ME),
                   git=replace(s.git, commits=(commit,)),
                   transcripts=replace(s.transcripts, calls=calls, messages=messages))


@pytest.mark.parametrize("source", ["commit", "result", "pending", "directive"])
@pytest.mark.parametrize("status", ["released", "approved", "new", "reopened", "blocked"])
def test_a_merged_change_is_closed_without_being_taken(
        tmp_path: Path, source: str, status: str) -> None:
    from operations import change_take, changes, merging, taking
    from operations.steps import Bash
    from ticketing.vocabulary import Status

    s = merged_state(tmp_path, source, status)
    t = s.tracker.tickets["9-1"]
    assert merging.merged(s, t)
    assert t.number in taking.purview(s)
    assert change_take.takeable(s) == []
    assert change_take.take(s) is None
    assert changes.held(s) == []
    step = changes.step(s, lambda *_: None)
    assert isinstance(step, Bash)
    args = shlex.split(step.command)
    assert args[4:10] == ["log", "9-1", "closed", "operator", "--from", status]
    assert "taking" not in step.command

    # Execute the generated transition against the tracker, including its
    # --from guard, and verify that no assignment was added to the log.
    number = script("ticket_numbers").ticket_number(args[5])
    moves = script("ticket_log").log_moves(tmp_path / "tickets", number, Status.CLOSED,
                                          args[7], Status(args[9]), None, args[10])
    closed = script("ticket_reads").held_ticket(moves.moved[0])
    assert closed.status is Status.CLOSED
    assert closed.log[:-1] == t.log


def test_a_merged_change_with_dependencies_is_not_left_waiting_to_be_taken(tmp_path: Path) -> None:
    from operations import change_take, changes
    from operations.steps import Bash

    s = merged_state(tmp_path, "directive")
    t = replace(s.tracker.tickets["9-1"], depends_on=("9-99",))
    s = replace(s, tracker=replace(s.tracker, tickets={t.number: t}),
                computed=replace(s.computed, budgets={}))
    assert change_take.ready(s) == []
    assert change_take.waiting(s) == []
    assert change_take.left(s) == {}
    assert isinstance(changes.step(s, lambda *_: None), Bash)


def test_a_merge_line_cannot_take_a_merged_blocked_change(tmp_path: Path) -> None:
    from operations import change_take, changes
    from operations.state import Message
    from operations.steps import Bash

    s = merged_state(tmp_path, "directive", "blocked")
    messages = (*s.transcripts.messages,
                Message(ME, s.now, None, "Op merge: 9-1.", stored=True))
    s = replace(s, transcripts=replace(s.transcripts, messages=messages))
    assert change_take.take(s) is None
    step = changes.step(s, lambda *_: None)
    assert isinstance(step, Bash) and "--from blocked" in step.command


def test_an_unassigned_merged_change_still_runs_its_after_merge_work(tmp_path: Path) -> None:
    from operations import changes
    from operations.roles import Role
    from operations.state import Agent, Report, Waits
    from operations.steps import Bash, Launch

    s = merged_state(tmp_path, "directive")
    t = replace(s.tracker.tickets["9-1"], after_merge="After the merge: check the result.")
    s = replace(s, tracker=replace(s.tracker, tickets={t.number: t}))
    step = changes.step(s, lambda *_: None)
    assert isinstance(step, Launch) and step.role is Role.AFTER_MERGE
    assert step.subject == t.number
    a = Agent(OTHER, ME, Role.AFTER_MERGE, t.number, step.brief, s.now, s.now,
              Waits.AT_WORK, (), True)
    running = replace(s, transcripts=replace(s.transcripts, agents=(a,)))
    assert changes.step(running, lambda *_: None) is None
    ended = replace(a, waits=None, reports=(Report(s.now + 10, "done"),))
    done = replace(s, transcripts=replace(s.transcripts, agents=(ended,)))
    step = changes.step(done, lambda *_: None)
    assert isinstance(step, Bash) and "--from released" in step.command
    assert changes.held(done) == []


@pytest.mark.parametrize("status", ["assigned", "closed"])
def test_unassigned_closing_leaves_held_and_closed_changes_alone(tmp_path: Path, status: str) -> None:
    from operations import changes

    s = merged_state(tmp_path, "directive", status)
    assert changes.closing(s) == []


def test_an_unmerged_released_change_can_still_be_taken(tmp_path: Path) -> None:
    from operations import change_take, changes
    from operations.steps import Bash

    s = state(tmp_path, {f"released/{NAME}": TAKEN + f"{FILED} released [operator]: released\n"},
              budgets=["9-1"])
    assert [t.number for t in change_take.takeable(s)] == ["9-1"]
    assert changes.closing(s) == []
    step = changes.step(s, lambda *_: None)
    assert isinstance(step, Bash) and "--from released" in step.command
    assert "taking:" in step.command
