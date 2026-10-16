"""The agents of a change: those launched on it, those of them in its
worktree, its editor roles that have none there, and what those launched
on it settled, which the brief of each agent launched on it gives
(`settled`).

The editors a change needs are those the `editors` field of its ticket
gives, which the ticket analyst that files it writes, and a change whose
ticket gives none is undecided. The agents of a change are those launched
since its last move out of `tickets/draft/`. Those an operator of
another session launched (`elsewhere_on`) are read apart: no step sends to
one, as `TranscriptsRead.elsewhere` gives why."""

from dataclasses import dataclass, replace
from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.change_budget import left_draft
from operations.change_holds import (LEFT_CHOICES, REVIEW_CHOICES, findings_hold, left_hold,
                                     questions_hold, unreplied_hold)
from operations.directives import Decision, decided
from operations.roles import EDITORS, Purpose, Role, analyst_of, subjects
from operations.state import Agent, Report, State, Ticket
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


def out_of_draft(state: State, number: str) -> float:
    """The time of the last move of the change `number` out of
    `tickets/draft/`, or 0.0 where its ticket is not read."""
    t = state.tracker.tickets.get(number)
    return 0.0 if t is None else left_draft(t)


def of_change(state: State, number: str) -> list[Agent]:
    """The agents `launched_on` gives for the change `number` since its
    last move out of `tickets/draft/`."""
    since = out_of_draft(state, number)
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


@dataclass(frozen=True)
class Reported:
    """An agent launched on a change, by its agent id, with its latest
    report."""
    agent_id: str
    report: Report


@dataclass(frozen=True)
class Ruled:
    """A hold of a change that a ruling decided with `choice`, which goes on
    past the hold, with the reply the hold rests on, where it rests on one."""
    hold: str
    choice: Decision
    meaning: str
    reply: Reported | None


@dataclass(frozen=True)
class Settled:
    """What the agents launched on change `number` settled before an agent
    of `role` is launched on it: the latest report of each of its ticket
    analysts, those of the other sessions' operators included
    (`analysts`); the latest report of each earlier agent of `role` there,
    for an editor only of its own part (`earlier`); and each hold of the
    change that a ruling decided with a choice that goes on past it
    (`ruled`)."""
    number: str
    role: Role
    analysts: tuple[Reported, ...]
    earlier: tuple[Reported, ...]
    ruled: tuple[Ruled, ...]


def reported(agents: list[Agent]) -> tuple[Reported, ...]:
    """Each of `agents` with an agent id and a report, in their order."""
    return tuple(Reported(a.agent_id, r) for a in agents
                 if a.agent_id is not None and (r := a.last_report) is not None)


def settled(state: State, number: str, role: Role, part: str | None) -> Settled:
    """What the agents launched on the change `number` since its last move
    out of `tickets/draft/` settled, for the brief of an agent of `role`
    launched on it, and, for an editor, of the part `part` as
    `briefs.part_of` gives it."""
    agents = of_change(state, number)
    since = out_of_draft(state, number)

    def of_roles(roles: tuple[Role, ...]) -> list[Agent]:
        return [a for a in with_elsewhere(state, number, agents, roles)
                if a.role in roles and a.launched > since]

    analysts = of_roles((Role.TICKET_ANALYST,))
    earlier: tuple[Reported, ...] = ()
    if role is not Role.TICKET_ANALYST:
        earlier = reported([a for a in of_roles((role,))
                            if role not in EDITORS or briefs.part_of(a) == part])
    holds: list[tuple[str, dict[Decision, str], Agent | None]] = []
    for a in analysts:
        if a.agent_id is None:
            continue
        if (hold := left_hold(a, number)) is not None:
            holds.append((hold, LEFT_CHOICES, a))
        holds.append((questions_hold(a, number), LEFT_CHOICES, a))
    for r in of_roles((Role.DOC_REVIEWER,)):
        if r.agent_id is not None:
            holds += [(findings_hold(r, number), REVIEW_CHOICES, r),
                      (unreplied_hold(r, number), REVIEW_CHOICES, None)]
    ruled: list[Ruled] = []
    for hold, choices, on in holds:
        choice = decided(state, hold, choices)
        if isinstance(choice, Decision) and choice is not Decision.AGAIN:
            reply = reported([on]) if on is not None else ()
            ruled.append(Ruled(hold, choice, choices[choice], reply[0] if reply else None))
    return Settled(number, role, tuple(reported(analysts)), earlier, tuple(ruled))


def with_before(s: Settled, before: Reported) -> Settled:
    """`s` with `before`, the earlier editor of another session that the
    `briefs.BEFORE` line of an editor's brief names, among `earlier`,
    whatever its launch time, so that the block gives the report that
    line refers to."""
    if any(r.agent_id == before.agent_id for r in s.earlier):
        return s
    return replace(s, earlier=(before, *s.earlier))
