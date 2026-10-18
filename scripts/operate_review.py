"""The `review` subcommand of `operate.py`: the step it prints for a code
editor or a doc editor, as `--help review` gives it."""

import sys
from pathlib import Path

from handbook.paths import console_importable, scripts_importable

console_importable()
scripts_importable()

from operator_transcript import read_operator  # noqa: E402
from state_assembly import read_state  # noqa: E402
from agent_reports import parent_type  # noqa: E402
from run_reads import parent_id  # noqa: E402
from transcripts import find  # noqa: E402
from transcript_snapshots import Refused  # noqa: E402
from tree_reads import main_tree  # noqa: E402
from ticket_files import ticket_path  # noqa: E402
from ticket_numbers import parsed_number  # noqa: E402
from ticket_reads import read_ticket  # noqa: E402
from filed_texts import written_report  # noqa: E402

from operations import changes  # noqa: E402
from operations.roles import LAUNCHING_EDITORS, Role  # noqa: E402
from operations.steps import Launch, Poll, Step, Undecided  # noqa: E402
from operate_loop import prepared, print_step, read_again, waited  # noqa: E402


def review(editor: str) -> int:
    """Print the step `changes.editor_step` gives the editor `editor`,
    read again within `operate_loop.waited` while it is `steps.Poll`, and
    once more where a worktree it reads is gone (`operate_loop.read_again`)."""
    path = find(editor)
    parent = parent_id(path)
    kind = parent_type(path)
    if kind != Role.OPERATOR.agent_type:
        print(changes.NO_OPERATOR.format(agent=editor))
        return 0
    filed = change_filed(parent, editor)

    def step_at(_deadline: float) -> tuple[Step | str, Path]:
        state, _ = read_state(parent, filed)
        return changes.editor_step(state, editor, written_report), state.scratch

    (step, scratch), _ = waited(editor, read_again(step_at), lambda out: not isinstance(out[0], Poll))
    if isinstance(step, str):
        print(step)
        return 0
    if isinstance(step, Undecided):
        print(f"operate: {step.text}", file=sys.stderr)
        return 1
    if not isinstance(step, (Launch, Poll)):
        raise TypeError(f"review step {step!r} is no launch")
    print_step(prepared(step, scratch), scratch, editor)
    return 0


def change_filed(operator: str, editor: str) -> float | None:
    """The time of the first log line of the change of the editor
    `editor`, of `roles.LAUNCHING_EDITORS`, as the launches of `operator`
    give that change, or None where they give no such launch or that
    ticket is not read."""
    agents = read_operator(operator, find(operator), main_tree(), [], {}).agents
    mine = [a for a in agents if a.agent_id == editor and a.role in LAUNCHING_EDITORS]
    number = parsed_number(mine[-1].subject) if mine else None
    if number is None:
        return None
    try:
        return read_ticket(ticket_path(main_tree() / "tickets", number)).filed
    except (Refused, ValueError, OSError):
        return None
