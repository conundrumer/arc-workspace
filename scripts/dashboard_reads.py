"""The reads the ticket dashboard (`ticket_dashboard`) renders from: the
recorded state of the main session's operator, and of a ticket its phrase,
the change it waits on, whether it is the user's and the stage of the work
on it; and the time a usage window reaches 100% at its rate so far."""

from collections.abc import Mapping
from enum import IntEnum
from pathlib import Path

from idle_sessions import named_main
from state_assembly import Shown, shown_read
from tree_reads import scratch

from operations.pacing import WINDOW_SECONDS, Usage, WindowName
from operations.roles import Role
from operations.state import Ticket
from operations.tracker import wait_line
from ticketing.vocabulary import COORDINATOR, Kind, Status

OPEN = frozenset(Status) - {Status.CLOSED, Status.DRAFT}
DAY = 86400.0

STALE_RECORD = 600.0
"""The age, in seconds, past which the operator's record reads as no
operator's read: a few minutes above the longest time between two full
reads of `operate.py next` (`operate_loop.FALLBACK_SECONDS`)."""


def operator_state(tickets: Path) -> Shown | str:
    """The state the last read of the main session's operator recorded
    (`state_assembly.write_shown`), or why there is none."""
    session = named_main(tickets)
    if session is None:
        return "no main session is set (`file_ticket.py main`)"
    return shown_read(scratch(session))


def served_request(t: Ticket, all_: Mapping[str, Ticket], seen: frozenset[str] = frozenset()) -> Ticket | None:
    """The first `request` the Motivation of `t` gives, followed through
    the `change` tickets it gives."""
    for m in t.motivation:
        r = all_.get(m)
        if r is None or m in seen:
            continue
        if r.kind is Kind.REQUEST:
            return r
        if r.kind is Kind.CHANGE and (found := served_request(r, all_, seen | {t.number, m})) is not None:
            return found
    return None


def phrase(t: Ticket, all_: Mapping[str, Ticket]) -> str:
    """The phrase of `t`: its Goal; else the Goal of `served_request`; else
    its title's text after its first `: `, up to its first `, ` or `;`,
    with its first letter capitalized."""
    r = served_request(t, all_)
    goal = t.goal if t.goal is not None else None if r is None else r.goal
    if goal is not None:
        return " ".join(goal.split())
    _, colon, after = t.title.partition(": ")
    cut = (after if colon else t.title).split(", ")[0].split(";")[0]
    return cut[:1].upper() + cut[1:]


def change_of(t: Ticket, all_: Mapping[str, Ticket]) -> Ticket | None:
    """The change the last wait line of `t`'s log gives, where the tracker
    holds it."""
    line = wait_line(t)
    return None if line is None or line.on_change is None else all_.get(line.on_change)


def users(t: Ticket, expedited: frozenset[str]) -> bool:
    """Whether `t` is the user's: the coordinator filed it, or it is
    expedited."""
    return t.filer == COORDINATOR or t.number in expedited


class Stage(IntEnum):
    """The stages of a ticket's work, in their order."""
    TRIAGE = 0
    DESIGN = 1
    BUILD = 2
    REVIEW = 3
    MERGE = 4


ROLE_STAGE: Mapping[Role, Stage] = {
    Role.TICKET_ANALYST: Stage.TRIAGE, Role.TRANSCRIPT_REVIEW: Stage.TRIAGE,
    Role.COST_AUDIT: Stage.TRIAGE, Role.LISTING_WAIT: Stage.TRIAGE, Role.OPERATOR: Stage.TRIAGE,
    Role.TICKET_REVIEWER: Stage.DESIGN, Role.DESIGN_REVIEWER: Stage.DESIGN,
    Role.CODE_EDITOR: Stage.BUILD, Role.DOC_EDITOR: Stage.BUILD, Role.HANDBOOK_EXPANDED: Stage.BUILD,
    Role.SOLVER_FIX: Stage.BUILD, Role.ANALYZE: Stage.BUILD, Role.CREATE: Stage.BUILD,
    Role.REFINE: Stage.BUILD,
    Role.ITEM_CHECKER: Stage.REVIEW, Role.CODE_REVIEWER: Stage.REVIEW, Role.DOC_REVIEWER: Stage.REVIEW,
    Role.LIB_REVIEWER: Stage.REVIEW, Role.GATE: Stage.REVIEW, Role.BATCH_PROFILE: Stage.REVIEW,
    Role.LOAD_CHECK: Stage.REVIEW,
    Role.AFTER_MERGE: Stage.MERGE,
}
"""The stage of the work an agent of each role does."""

assert set(ROLE_STAGE) == set(Role), "each role has a stage"


def stage(roles: list[Role], change: Ticket | None) -> Stage:
    """The stage of a ticket at whose work, or that of its change
    `change`, agents of `roles` are: the highest of theirs, and at least
    Design for a change in `tickets/draft/` and Build for a change past
    it."""
    floor = (Stage.TRIAGE if change is None or change.kind is not Kind.CHANGE
             else Stage.DESIGN if change.status is Status.DRAFT else Stage.BUILD)
    return max([floor, *(ROLE_STAGE[r] for r in roles)])


def hits_full(usage: Usage, name: WindowName) -> float | None:
    """The time the window `name` reaches 100% at its rate so far, where
    that is before its reset; None where the usage gives no such window or
    no use of it."""
    w = usage.windows.get(name)
    if w is None or w.used_pct <= 0:
        return None
    start = w.resets_at - WINDOW_SECONDS[name]
    if usage.now <= start:
        return None
    at = usage.now + (100 - w.used_pct) * (usage.now - start) / w.used_pct
    return at if at < w.resets_at else None
