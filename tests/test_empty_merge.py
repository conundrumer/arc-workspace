"""An empty merge refuses to proceed without a readiness ruling."""

import dataclasses
from pathlib import Path

import pytest

from tests.test_unreported_agents import CHANGE_LOG, FIRST, ME, agent, state, ticket

BACK = ("2026-10-17T03:00:00Z blocked [operator {me}]: blocked\n"
        "2026-10-17T03:10:00Z assigned [operator {me}]: unblocked\n")


@pytest.mark.parametrize("reported, back, held", [
    (False, False, True),
    (True, False, True),
    (True, True, False),
])
def test_an_empty_change_goes_to_an_analyst(tmp_path: Path, reported: bool, back: bool,
                                            held: bool) -> None:
    from operations import briefs
    from operations.merging import NO_CHANGE, REFUSED, merge_command, merge_steps
    from operations.roles import Role
    from operations.state import Call, Merge, Tool
    from operations.steps import Bash, Undecided
    w = tmp_path / "main" / ".claude" / "worktrees" / "change-9-1"
    text = ("---\nkind: change\neditors: code-editor\n---\n# x: y\n\n"
            + CHANGE_LOG.format(me=ME, w=w) + (BACK.format(me=ME) if back else ""))
    t = ticket(tmp_path, "assigned", "9-1_change_x_ticket-analyst.md", text)
    at = t.log[3].time + 100
    refusal = REFUSED + NO_CHANGE.format(branch="change-9-1", base="master")
    call = Call(ME, at, Tool.BASH, {"command": merge_command(t, w)}, refusal + "\n", False,
                Merge.REFUSED)
    editor = agent(FIRST, Role.CODE_EDITOR, t.number, briefs.WORK_IN.format(worktree=w),
                   at - 50, at + 60, [at + 50] if reported else [at - 10])
    s = state(tmp_path, [t], [editor], w)
    s = dataclasses.replace(s, transcripts=dataclasses.replace(s.transcripts, calls=(call,)))
    step = merge_steps(s, t, w, [editor], lambda _: None)
    if held:
        assert isinstance(step, Undecided) and step.ruling
    else:
        assert isinstance(step, Bash) and step.command == merge_command(t, w)
