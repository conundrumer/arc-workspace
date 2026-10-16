"""The agents of a change: those launched on it, those of them in its
worktree, and its editor roles that have none there.

The editors a change needs are those the `editors` field of its ticket
gives, which the ticket analyst that files it writes, and a change whose
ticket gives none is undecided. The agents of a change are those launched
since its last move out of `tickets/draft/`. Those an operator of
another session launched (`elsewhere_on`) are read apart: no step sends to
one, as `TranscriptsRead.elsewhere` gives why."""

from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.change_budget import left_draft
from operations.roles import EDITORS, Purpose, Role, analyst_of, subjects
from operations.state import Agent, State, Ticket
from operations.steps import Undecided


def on_change(a: Agent, number: str) -> bool:
    """Whether `a` is an editor, a doc reviewer, an item checker or a
    ticket analyst launched on the change `number`."""
    if a.role is Role.TICKET_ANALYST:
        parsed = analyst_of(a.subject)
        return parsed is not None and parsed[0] is Purpose.CHANGE \
            and number in subjects(parsed[1])
    return a.role in (*EDITORS, Role.DOC_REVIEWER, Role.ITEM_CHECKER) and a.subject == number


def launched_on(state: State, number: str) -> list[Agent]:
    """The agents of the session's operators launched on the change
    `number`, as `on_change` gives them."""
    return [a for a in state.transcripts.agents if on_change(a, number)]


def elsewhere_on(state: State, number: str) -> list[Agent]:
    """The agents of `TranscriptsRead.elsewhere` on the change `number`."""
    return [a for a in state.transcripts.elsewhere if on_change(a, number)]


def with_elsewhere(state: State, number: str, agents: list[Agent],
                   roles: tuple[Role, ...]) -> list[Agent]:
    """`agents`, the agents of the change `number`, with those of
    `elsewhere_on` of `roles` added, in the order of their launch."""
    return sorted([*agents, *(a for a in elsewhere_on(state, number) if a.role in roles)],
                  key=lambda a: a.launched)


def of_change(state: State, number: str) -> list[Agent]:
    """The agents `launched_on` gives for the change `number` since its
    last move out of `tickets/draft/`."""
    t = state.tracker.tickets.get(number)
    since = 0.0 if t is None else left_draft(t)
    return [a for a in launched_on(state, number) if a.launched > since]


def in_worktree(a: Agent, w: Path) -> bool:
    return briefs.WORK_IN.format(worktree=w) in a.brief


def editors_in(agents: list[Agent], w: Path) -> list[Agent]:
    """The editors among `agents` launched in the worktree `w`."""
    return [a for a in agents if a.role in EDITORS and in_worktree(a, w)]


def change_editors(t: Ticket) -> tuple[Role, ...] | Undecided:
    """The editors of the change `t`, those its `editors` field gives; a
    change whose ticket gives none is undecided."""
    if t.editors is None:
        return Undecided(mctx("change {number} gives no `editors` field").format(
            number=t.number))
    return t.editors


def unstaffed(editors: tuple[Role, ...], here: list[Agent]) -> list[Role]:
    """The editor roles of `editors` with no agent among `here`, the
    editors in the change's worktree, in the order of `EDITORS`."""
    return [r for r in EDITORS if r in editors and not any(a.role is r for a in here)]


def latest_editors(here: list[Agent]) -> list[Agent]:
    """The latest editor of `here` of each role, with the doc editor of
    the fragments (`briefs.FRAGMENTS_PART`) apart from the doc editor of
    the documents."""
    return list({(a.role, briefs.FRAGMENTS_PART in a.brief): a for a in here}.values())
