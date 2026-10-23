"""The `review` subcommand of `operate.py`: the step it prints for a code
editor or a doc editor, as `--help review` gives it. Each call of an
eligible editor counts: the time of its report is the time of the anchor of
its work (`review_anchor`), which each read of the state in the call writes
anew where the fingerprint of that work has changed."""

import sys
from pathlib import Path

from handbook.paths import scripts_importable

scripts_importable()

from operator_transcript import read_operator  # noqa: E402
from review_anchor import anchored, fingerprint  # noqa: E402
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
from operate_loop import MessageAccepted, Running, prepared, print_step, read_again, waited  # noqa: E402

def qualification(editor: str) -> str | None:
    """Return the current eligible editor's parent, or print its refusal."""
    from codex_reads import native_find
    from run_reads import agent_type

    native = native_find(editor)
    if native is not None:
        parent = native.assignment.operator
        kind = agent_type(find(parent))
    else:
        path = find(editor)
        parent = parent_id(path)
        kind = parent_type(path)
    if kind != Role.OPERATOR.agent_type:
        print(changes.NO_OPERATOR.format(agent=editor))
        return None
    return parent


def plan(editor: str) -> tuple[Launch, Path] | int:
    """Read current qualification and state, without preparing a launch."""
    from state_reads import new_state

    new_state()
    parent = qualification(editor)
    if parent is None:
        return 0
    filed = change_filed(parent, editor)

    def step_at(_deadline: float) -> tuple[Step | str, Path]:
        state, _ = read_state(parent, filed)
        def anchoring(agent: str, current: str, now: float) -> float:
            return anchored(state.scratch, agent, current, now)

        return (changes.editor_step(state, editor, written_report, fingerprint, anchoring),
                state.scratch)

    outcome = waited(editor, read_again(step_at), lambda out: not isinstance(out[0], Poll))
    if isinstance(outcome, MessageAccepted):
        from operations.printing import printed
        print(printed(Poll(), editor, Path()))
        return 0
    if isinstance(outcome, Running):
        print(outcome.text())
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
    if isinstance(step, Poll):
        from operations.printing import printed
        print(printed(step, editor, scratch))
        return 0
    return step, scratch


def publish(editor: str, step: Launch, scratch: Path) -> int:
    """Prepare and publish a review launch in the foreground caller."""
    from codex_reads import native_find

    native = native_find(editor)
    ready = prepared(step, scratch)
    if native is not None and isinstance(ready, Launch):
        import json
        from codex_ticket import prepare
        from operations.filing import filed as filed_steps, filed_line
        from operations.roles import CLAUDE_TYPES, agent_type, description, launch_parameters

        if agent_type(ready.role, ready.subject) in CLAUDE_TYPES:
            for target, text in filed_steps(ready, scratch).items():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text + "\n")
            parameters = {**launch_parameters(ready.role, ready.subject, ready.model,
                                             filed_line(ready, scratch)),
                          "run_in_background": True}
        else:
            parameters = {"description": description(ready.role, ready.subject),
                          "prompt": ready.brief}
            if ready.model is not None:
                parameters["model"] = ready.model.value
        print(json.dumps(prepare(native.assignment.scratch, parameters, Path.home())))
        return 0
    print_step(ready, scratch, editor)
    return 0


def review(editor: str) -> int:
    """Plan and publish a direct review using current editor qualification."""
    outcome = plan(editor)
    return outcome if isinstance(outcome, int) else publish(editor, *outcome)


def change_filed(operator: str, editor: str) -> float | None:
    """The time of the first log line of the change of the editor
    `editor`, of `roles.LAUNCHING_EDITORS`, as the launches of `operator`
    give that change, or None where they give no such launch or that
    ticket is not read."""
    from codex_reads import native_find

    native = native_find(editor)
    if native is not None:
        number = parsed_number(native.assignment.subject or native.assignment.ticket)
    else:
        agents = read_operator(operator, find(operator), main_tree(), [], {}).agents
        mine = [a for a in agents if a.agent_id == editor and a.role in LAUNCHING_EDITORS]
        number = parsed_number(mine[-1].subject) if mine else None
    if number is None:
        return None
    try:
        return read_ticket(ticket_path(main_tree() / "tickets", number)).filed
    except (Refused, ValueError, OSError):
        return None
