"""The `review` subcommand of `operate.py`: the step it prints for a code
editor or a doc editor, as `--help review` gives it, or, for a call that
`Agent.reviewing` does not count, the form of the call it counts."""

import sys
from pathlib import Path

from handbook.paths import console_importable, scripts_importable

console_importable()
scripts_importable()

from operator_transcript import read_operator, reviewing_since  # noqa: E402
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
from operations.command_words import Action, next_command  # noqa: E402
from operations.roles import LAUNCHING_EDITORS, Role  # noqa: E402
from operations.steps import Launch, Poll, Step, Undecided  # noqa: E402
from operate_loop import MessageAccepted, prepared, print_step, read_again, waited  # noqa: E402

from controlled_markdown import mctx  # noqa: E402


UNCOUNTED = mctx("This call is not counted as your `review` call. A `review` call counts only "
                 "where its words stand as a command of their own, with no word such as "
                 "`timeout` before them, and only while no other tool call follows it. "
                 "Run `{command}` so, in a foreground Bash call, and do as it prints.")
"""The line `review` prints for a call that `Agent.reviewing` does not count,
with `command` the call that counts."""


def review(editor: str) -> int:
    """Print the step `changes.editor_step` gives the editor `editor`,
    read again within `operate_loop.waited` while it is `steps.Poll`, and
    once more where a worktree or a file it reads is gone
    (`operate_loop.read_again`).

    Where `Agent.reviewing` of the editor, as its transcript stands when
    the call starts, does not count the call, it prints `UNCOUNTED` instead,
    with no block and no read of the state."""
    path = find(editor)
    parent = parent_id(path)
    kind = parent_type(path)
    if kind != Role.OPERATOR.agent_type:
        print(changes.NO_OPERATOR.format(agent=editor))
        return 0
    if reviewing_since(path, editor) is None:
        print(UNCOUNTED.format(command=next_command(editor, Action.REVIEW)))
        return 0
    filed = change_filed(parent, editor)

    def step_at(_deadline: float) -> tuple[Step | str, Path]:
        state, _ = read_state(parent, filed)
        return changes.editor_step(state, editor, written_report), state.scratch

    outcome = waited(editor, read_again(step_at), lambda out: not isinstance(out[0], Poll))
    if isinstance(outcome, MessageAccepted):
        print_step(Poll(), Path(), editor)
        return 0
    step, scratch = outcome
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
