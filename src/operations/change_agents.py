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

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.completion import finished, occupies
from operations.change_budget import left_draft, taken
from operations.change_holds import (Hold, findings_hold, left_hold, questions_hold,
                                     unreplied_hold)
from operations.directives import Decision, Ruling, ruling
from operations.roles import EDITORS, Purpose, Role, analyst_of, subjects
from operations.state import Agent, Report, State, Ticket, memoized_by_transcripts
from operations.steps import NoStep, Step, Undecided
from ticketing.times import utc_stamp

REVIEWER_ROLES = (Role.DOC_REVIEWER, Role.DESIGN_REVIEWER, Role.ITEM_CHECKER)
"""The roles of the reviewers of a change."""


def changes_of(a: Agent) -> list[str]:
    """The changes `a` was launched on, as an editor, a reviewer
    (`REVIEWER_ROLES`) or a ticket analyst."""
    if a.role is Role.TICKET_ANALYST:
        parsed = analyst_of(a.subject)
        return subjects(parsed[1]) if parsed is not None and parsed[0] is Purpose.CHANGE else []
    return [a.subject] if a.role in (*EDITORS, *REVIEWER_ROLES) else []


def on_change(a: Agent, number: str) -> bool:
    """Whether `a` was launched on the change `number` (`changes_of`)."""
    return number in changes_of(a)


@memoized_by_transcripts
def agents_by_change(state: State) -> Mapping[str, tuple[Agent, ...]]:
    """The agents of the session's operators launched on each change
    (`changes_of`), by its number, in the order of
    `TranscriptsRead.agents`."""
    out: dict[str, list[Agent]] = {}
    for a in state.transcripts.agents:
        for n in dict.fromkeys(changes_of(a)):
            out.setdefault(n, []).append(a)
    return {n: tuple(agents) for n, agents in out.items()}


def latest_of_role(agents: list[Agent], role: Role, since: float, number: str,
                   launch: Callable[[], Step]) -> Step | None:
    """The step on the latest of the agents of `role` among `agents`, those
    of the change `number`, launched after `since`: `launch` where there
    is no active or completed attempt, and otherwise None."""
    found = [a for a in agents if a.role is role and a.launched > since]
    if not found or not occupies(found[-1]):
        return launch()
    return None


def named(agents: list[Agent]) -> str:
    """`agents`, each by its role and agent id."""
    return ", ".join(f"{a.role} {a.agent_id or 'with no known id'}" for a in agents)


def waiting_on(agents: list[Agent]) -> NoStep:
    """The wait on `agents`, which are at work, with the time of the
    latest of their launches and last resumes."""
    return NoStep(mctx("waits on {agents}, at work since {time}").format(
        agents=named(agents), time=utc_stamp(max(a.since for a in agents))))


def worktree_occasion(t: Ticket, w: Path) -> str:
    """The `occasion` of a launch on the change `t` in its worktree `w`."""
    return f"{w} {t.taken}"


def launched_on(state: State, number: str) -> list[Agent]:
    """The agents of the session's operators launched on the change
    `number`, as `on_change` gives them."""
    return list(agents_by_change(state).get(number, ()))


def elsewhere_on(state: State, number: str) -> list[Agent]:
    """The agents of `TranscriptsRead.elsewhere` on the change `number`."""
    return [a for a in state.transcripts.elsewhere if on_change(a, number)]


def with_elsewhere(state: State, number: str, agents: list[Agent],
                   roles: tuple[Role, ...]) -> list[Agent]:
    """`agents`, the agents of the change `number`, with those of
    `elsewhere_on` of `roles` added, in the order of their launch."""
    return sorted([*agents, *(a for a in elsewhere_on(state, number) if a.role in roles)],
                  key=lambda a: a.launched)


def of_change(state: State, t: Ticket) -> list[Agent]:
    """The agents `launched_on` gives for the change `t` since its last
    move out of `tickets/draft/`."""
    since = left_draft(t)
    return [a for a in launched_on(state, t.number) if a.launched > since]


def since_take(state: State, t: Ticket) -> list[Agent]:
    """The agents of the change `t`, those `of_change` gives and those of
    `elsewhere_on`, launched since its latest take, or since its last move
    out of `tickets/draft/` where no take applies."""
    take = taken(t)
    since = left_draft(t) if take is None else take.time
    return [a for a in (*of_change(state, t), *elsewhere_on(state, t.number))
            if a.launched > since]


def of_roles_since_draft(state: State, t: Ticket, roles: tuple[Role, ...]) -> list[Agent]:
    """The agents of `roles` launched on the change `t` since its last move
    out of `tickets/draft/`, those of other sessions included, in the order
    of their launch."""
    since = left_draft(t)
    return [a for a in with_elsewhere(state, t.number, of_change(state, t), roles)
            if a.role in roles and a.launched > since]


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
    editors in the change's worktree, or whose latest attempt in a part
    stopped without a result, in the order of `EDITORS`."""
    latest = latest_editors([a for a in here if not briefs.gives_fragments_alone(a.brief)])
    return [r for r in EDITORS if r in editors and (
        not any(a.role is r for a in latest)
        or any(a.role is r and not occupies(a) for a in latest))]


def editor_part(a: Agent) -> tuple[Role, bool]:
    """The editor's part key, with the doc editor of the fragments apart
    from the doc editor of the documents."""
    return a.role, briefs.gives_fragments_alone(a.brief)


def latest_editors(here: list[Agent]) -> list[Agent]:
    """The latest editor of `here` of each role, with the doc editor of
    the fragments (`briefs.FRAGMENTS_PART`) apart from the doc editor of
    the documents."""
    return list({editor_part(a): a for a in here}.values())


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
    for an editor only of its own part (`earlier`); whether an earlier
    agent of `role` there, for an editor only of its own part, was
    launched and still occupies its work (`launched_before`); and each hold
    of the change that a ruling decided with a choice that goes on past it
    (`ruled`)."""
    number: str
    role: Role
    analysts: tuple[Reported, ...]
    earlier: tuple[Reported, ...]
    launched_before: bool
    ruled: tuple[Ruled, ...]


def reported_at(a: Agent, w: Path, fingerprint: Callable[[Path, Path], str]) -> float | None:
    """The time from which the editor `a`, with its worktree `w`, has
    reported, as `changes.editor_step` reads it: for one that waits, the
    time of its `Agent.reviewing` where the fingerprint of its work, as
    `fingerprint` gives it for the worktree and the report file, equals
    the anchor's, and None otherwise; for one that no longer waits, the
    time of its last report, or None where it has not reported. A
    `ValueError` of `fingerprint` is raised."""
    if a.pending:
        if a.reviewing is None or a.report_file is None:
            return None
        return a.reviewing.at if fingerprint(w, a.report_file) == a.reviewing.fingerprint else None
    return None if (r := a.last_report) is None else r.time


def reported(agents: list[Agent]) -> tuple[Reported, ...]:
    return tuple(Reported(a.agent_id, r) for a in agents
                 if a.agent_id is not None and finished(a) and (r := a.last_report) is not None)


def settled(state: State, t: Ticket, role: Role, part: briefs.Part | None) -> Settled:
    """What the agents launched on the change `t` since its last move out
    of `tickets/draft/` settled, for the brief of an agent of `role`
    launched on it, and, for an editor, of the part `part` as
    `briefs.part_of` gives it."""
    number = t.number

    def of_roles(roles: tuple[Role, ...]) -> list[Agent]:
        return of_roles_since_draft(state, t, roles)

    analysts = of_roles((Role.TICKET_ANALYST,))
    earlier: tuple[Reported, ...] = ()
    before: list[Agent] = []
    if role is not Role.TICKET_ANALYST:
        before = [a for a in of_roles((role,))
                  if role not in EDITORS or briefs.part_of(a) is part]
        earlier = reported(before)
    holds: list[tuple[Hold, Agent | None]] = []
    for a in analysts:
        if a.agent_id is None:
            continue
        if (hold := left_hold(a, number)) is not None:
            holds.append((hold, a))
        holds.append((questions_hold(a, number), a))
    for r in of_roles((Role.DOC_REVIEWER,)):
        if r.agent_id is not None:
            holds += [(findings_hold(r, number), r), (unreplied_hold(r, number), None)]
    ruled: list[Ruled] = []
    for hold, on in holds:
        given = ruling(state, hold.text, hold.choices)
        if isinstance(given, Ruling) and given.choice is not Decision.AGAIN:
            reply = reported([on]) if on is not None else ()
            ruled.append(Ruled(hold.text, given.choice, hold.choices[given.choice],
                               reply[0] if reply else None))
    return Settled(number, role, tuple(reported(analysts)), earlier, any(occupies(a) for a in before),
                   tuple(ruled))


def with_before(s: Settled, before: Reported) -> Settled:
    """`s` with `before`, the earlier editor of another session that the
    `briefs.BEFORE` line of an editor's brief names, among `earlier`,
    whatever its launch time, so that the block gives the report that
    line refers to."""
    if any(r.agent_id == before.agent_id for r in s.earlier):
        return s
    return replace(s, earlier=(before, *s.earlier))
