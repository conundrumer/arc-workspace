"""The tickets that stall, and the move to `tickets/draft/` of a change
that waits on a ticket that holds it up.

A ticket of `taking.scope` is stalled (`stalled`) where an operator's step
is due on it and it has made no progress for `STUCK_SECONDS`, whatever the
cause that held it. A step is due on it by an exit of `tracker.exits` that
an operator's step makes, read by the function that step selects its work
by (`selection`); a ticket whose only exits are steps of no operator, or
that such a function leaves out, waits by design and is not due. A ticket
that a live holder outside the session's own agent runs holds waits on
that holder's work, a step of no operator, which the operators'
transcripts do not show and which that holder's own session watches, and
is not due. Its progress is a line of its log other than a
take or a release, the first take after such progress, the launch of an
agent of it, a report of such an agent, and, for a change, its merge onto
`master`; an agent of it that is pending and not quiet is progress too,
and a ticket with one is not stalled.

A change that waits for a ticket that holds it up (`holding`), one under
`tickets/blocked/` or one that is stalled, moves to `tickets/draft/` with
a line whose note is `taking.STALL_FINDING` on that ticket, once after the
time from which that ticket holds it up (`stall`)."""

import re
from collections.abc import Mapping
from typing import assert_never

from controlled_markdown import mctx
from operations import drafts, lineage, merging, taking, triage
from operations.change_budget import TAKEN
from operations.constants import stuck_reached
from operations.final_reply import live_holder
from operations.log_commands import log
from operations.roles import AGENT_ID
from operations.state import Agent, State, Ticket
from operations.steps import Bash, Step
from operations.tracker import blocked_on_user, exits
from ticketing.exits import Exit
from ticketing.times import utc_stamp
from ticketing.vocabulary import Kind, Status


ON_USER = mctx("it waits on the user")
NO_STEP = mctx("it has had no step since {time}")


def held_outside_session(state: State, t: Ticket) -> bool:
    return (t.holder is not None and live_holder(state, t.holder)
            and (re.fullmatch(AGENT_ID, t.holder) is None
                 or t.holder not in state.session_holders))


def selection(state: State, e: Exit) -> set[str]:
    """The tickets on which the step that makes `e` is due, as the function
    that step selects its work by gives them, or none where no operator's
    step makes `e`."""
    match e:
        case Exit.HOLDER | Exit.RELEASE:
            return {n for n, t in state.tracker.tickets.items()
                    if t.status is Status.ASSIGNED and not held_outside_session(state, t)}
        case Exit.TAKE:
            return {t.number for t in taking.takeable(state)}
        case Exit.TICKET_REVIEW:
            return drafts.due(state)
        case Exit.TICKET_ANALYST:
            return set(triage.selected(state))
        case (Exit.MERGE | Exit.CHANGE_ANALYST | Exit.COORDINATOR_MOVE | Exit.COORDINATOR_LINE
              | Exit.MERGE_LINE | Exit.CHANGE_CLOSE | Exit.SWEEP):
            return set()
        case _:
            assert_never(e)


def agents_of(state: State, number: str) -> list[Agent]:
    return [a for a in state.transcripts.agents if number in lineage.tickets(a.role, a.subject)]


def progress(state: State, t: Ticket) -> float | None:
    """The time of `t`'s last progress, or None where an agent of it is
    at work."""
    agents = agents_of(state, t.number)
    if any(a.pending and a.agent_id not in state.transcripts.quiet for a in agents):
        return None
    merge = merging.merge_commit(state, t) if t.kind is Kind.CHANGE else None
    last: float = max([t.filed,
                       *([merge.time] if merge is not None else []),
                       *(ln.time for ln in t.log
                         if TAKEN.fullmatch(ln.note) is None and taking.RELEASED_LINE.fullmatch(ln.note) is None),
                       *(a.launched for a in agents),
                       *(r.time for a in agents for r in a.reports)])
    return next((ln.time for ln in t.log
                 if ln.time > last and TAKEN.fullmatch(ln.note) is not None), last)


def stalled(state: State) -> dict[str, float]:
    """The stalled tickets, with the time of their last progress: an
    operator's step is due on each."""
    selections: dict[Exit, set[str]] = {}
    out: dict[str, float] = {}
    for n in sorted(taking.scope(state)):
        t = state.tracker.tickets.get(n)
        if t is None:
            continue
        due = False
        for e in sorted(exits(state, t).by):
            if e not in selections:
                selections[e] = selection(state, e)
            due = due or n in selections[e]
        if due and (last := progress(state, t)) is not None and stuck_reached(last, state.now):
            out[n] = last
    return out


def holding(state: State, u: Ticket, stalls: Mapping[str, float]) -> tuple[float, str] | None:
    """The time from which `u` holds up the changes that wait on it, with
    the reason, where it does: from its last move into `tickets/blocked/`
    where it waits on the user, and otherwise from its last progress where
    `stalls`, as `stalled` gives them, holds it."""
    if blocked_on_user(u) is not None:
        return taking.blocked_since(u), ON_USER
    if u.number in stalls:
        since = stalls[u.number]
        return since, NO_STEP.format(time=utc_stamp(since))
    return None


def stall(state: State) -> Step | None:
    """The move to `tickets/draft/` of a change that `waiting()` gives that
    waits for a ticket that `holding` gives, where no line of its log
    since the time `holding` gives gives `taking.STALL_FINDING` on it."""
    stalls = stalled(state)
    for n, deps in taking.waiting(state):
        t = state.tracker.tickets[n]
        for d in deps:
            u = state.tracker.tickets.get(d)
            held_up = None if u is None else holding(state, u, stalls)
            if held_up is None:
                continue
            since, reason = held_up
            if not any(ln.time >= since and (m := taking.STALLED.match(ln.note)) is not None
                       and m["number"] == d for ln in t.log):
                return Bash(log(n, Status.DRAFT, Status.OPEN,
                                taking.STALL_FINDING.format(number=d, reason=reason), state.me))
    return None
