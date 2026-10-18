"""The `review` subcommand of `operate.py`: the step it prints for a doc
editor, as `--help review` gives it."""

import sys

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

from operations import doc_review  # noqa: E402
from operations.roles import Role  # noqa: E402
from operations.steps import Launch, Undecided  # noqa: E402
from operate_loop import prepared, print_step  # noqa: E402


def review(editor: str) -> int:
    """Print the step `doc_review.editor_review` gives the doc editor
    `editor`."""
    path = find(editor)
    parent = parent_id(path)
    kind = parent_type(path)
    if kind != Role.OPERATOR.agent_type:
        print(doc_review.NO_OPERATOR.format(agent=editor))
        return 0
    state, _ = read_state(parent, change_filed(parent, editor))
    step = doc_review.editor_review(state, editor)
    if isinstance(step, str):
        print(step)
        return 0
    if isinstance(step, Undecided):
        print(f"operate: {step.text}", file=sys.stderr)
        return 1
    if not isinstance(step, Launch):
        raise TypeError(f"review step {step!r} is no launch")
    print_step(prepared(step, state.scratch), state.scratch, editor)
    return 0


def change_filed(operator: str, editor: str) -> float | None:
    """The time of the first log line of the change of the doc editor
    `editor`, as the launches of `operator` give that change, or None where
    they give no such launch or that ticket is not read."""
    agents = read_operator(operator, find(operator), main_tree(), [], {}).agents
    mine = [a for a in agents if a.agent_id == editor and a.role is Role.DOC_EDITOR]
    number = parsed_number(mine[-1].subject) if mine else None
    if number is None:
        return None
    try:
        return read_ticket(ticket_path(main_tree() / "tickets", number)).filed
    except (Refused, ValueError, OSError):
        return None
