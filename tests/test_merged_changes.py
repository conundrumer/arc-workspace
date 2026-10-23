"""Merged changes finish their closing sequence without another take."""

from dataclasses import replace
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("status", ["assigned", "closed"])
def test_unassigned_closing_leaves_held_and_closed_changes_alone(tmp_path: Path, status: str) -> None:
    from operations import changes

    s = merged_state(tmp_path, "directive", status)
    assert changes.closing(s) == []


