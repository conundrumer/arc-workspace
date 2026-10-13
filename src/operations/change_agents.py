"""The agents of a change: those launched on it, those of them in its
worktree, and its editor roles that have none there.

The editors a change needs are those the `editors` field of its ticket
gives, which the ticket analyst that files it writes, and a change whose
ticket gives none is undecided. The agents of a change are those launched
since its last move out of `tickets/draft/`."""

from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.change_budget import left_draft
from operations.roles import EDITORS, Purpose, Role
from operations.state import Agent, State, Ticket
from operations.steps import Undecided


def launched_on(state: State, number: str) -> list[Agent]:
    """The editors, doc reviewers, item checkers and ticket analysts
    launched on the change `number`."""
    roles = (*EDITORS, Role.DOC_REVIEWER, Role.ITEM_CHECKER)
    out = [a for a in state.transcripts.agents if a.role in roles and a.subject == number]
    out += [a for a, p, nums in state.analysts() if p is Purpose.CHANGE and number in nums]
    return sorted(out, key=lambda a: a.launched)


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
