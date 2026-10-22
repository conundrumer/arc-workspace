"""The tickets that wait on nothing that moves them, and the message on
them to the coordinator.

A ticket of `taking.purview` outside `tickets/closed/` is a candidate
(`candidates`) where, at a read of the state, no agent of it is pending
(`ticket_stall.agents_of`), no entry of its `depends-on` stands outside
`tickets/closed/`, and none of its exits (`tracker.exits`) has a party
that moves it at that read (`party`): an operator's step due on it by
that exit, or the party the step logic names where it gives no such step
(`named`), where that party stands (`parties.stands`). The check reads
only these, and no cause that left the ticket so.

The time from which a candidate has stood so is the time of the first
read of the state, by an operator of the session, of those since which
each such read found it a candidate, as `State.unwaited_since` records it
with the time of the last read that found it one (`times`). A read drops
the time of a ticket that is no candidate, and an entry whose last read
is `TICKET_STUCK_SECONDS` or more before the read at hand is lost. A candidate
waits on nothing (`unwaited`) once that time is `AGAIN_SECONDS` or more
before the read: a shorter stretch can be the lag of one read, or the
operator's own move of a wait on to the next change of a chain.

The tickets that wait on nothing get one message to the coordinator for
those of them it has not yet given, once per stretch, and each is then
recorded in one `bug` ticket of its own kind (`alerts.BugKind.UNWAITED`),
by `step`."""

from collections.abc import Mapping

from controlled_markdown import mctx
from operations import alerts, taking, ticket_stall
from operations.constants import AGAIN_SECONDS, COORDINATOR
from operations.handled import repeated
from operations.parties import ByExit, OnTicket, Party, stands
from operations.state import DueEntry, State, Ticket, memoized
from operations.steps import Send, Step
from operations.tracker import closed, exits, wait_line
from ticketing.exits import Exit
from ticketing.times import utc_stamp
from ticketing.vocabulary import Domain, Status

OPENING = mctx("Ticket {number} waits on nothing that moves it:")
"""The line that opens the part of the message to the coordinator on one
ticket, by which `told` finds that part in a message sent."""


def due(state: State, t: Ticket, e: Exit) -> bool:
    """Whether an operator's step is due on `t` by the exit `e`
    (`ticket_stall.selection`)."""
    return t.number in ticket_stall.selection(state, e)


def named(state: State, t: Ticket, e: Exit) -> Party | None:
    """The party the exit `e` of `t` waits on where no operator's step is
    due on `t` by `e` (`ticket_stall.selection`), as the step logic names
    it (`ticket_stall.party`): for `CHANGE_CLOSE`, the change the last
    wait line gives; for `COORDINATOR_LINE`, the coordinator, outside
    `tickets/waiting/`; for any other exit no operator's step makes, the
    party of that exit. None where a step is due or none is named."""
    if due(state, t, e):
        return None
    match e:
        case Exit.TAKE | Exit.TICKET_ANALYST | Exit.TICKET_REVIEW | Exit.RELEASE | Exit.HOLDER:
            return ticket_stall.party(state, e, t)
        case Exit.CHANGE_CLOSE:
            line = wait_line(t)
            return None if line is None or line.on_change is None else OnTicket(line.on_change)
        case Exit.COORDINATOR_LINE:
            return None if t.status is Status.WAITING else ByExit(e)
        case Exit.CHANGE_ANALYST | Exit.MERGE | Exit.COORDINATOR_MOVE | Exit.MERGE_LINE | Exit.SWEEP:
            return ByExit(e)


def party(state: State, t: Ticket, e: Exit) -> bool:
    """Whether the exit `e` of `t` has a party that moves `t` at the read
    that gave `state`: an operator's step due on it by `e`, or the party
    of `named` where it stands (`parties.stands`)."""
    if due(state, t, e):
        return True
    p = named(state, t, e)
    return p is not None and stands(state, p)


@memoized
def candidates(state: State) -> frozenset[str]:
    """The tickets of `taking.purview` outside `tickets/closed/` with no
    agent pending, no open entry of their `depends-on`, and no exit with a
    party at the read that gave `state`."""
    out: set[str] = set()
    for n in sorted(taking.purview(state)):
        t = state.tracker.tickets.get(n)
        if t is None or t.status is Status.CLOSED:
            continue
        if any(a.pending for a in ticket_stall.agents_of(state, n)):
            continue
        if not all(closed(state, d) for d in t.depends_on):
            continue
        if not any(party(state, t, e) for e in sorted(exits(state, t).by)):
            out.add(n)
    return frozenset(out)


def times(state: State) -> dict[str, DueEntry]:
    """The record of the times from which each candidate has stood so,
    after the read that gave `state`: for each ticket of `candidates`, its
    time in the live entries of `State.unwaited_since`, or `state.now`
    where those hold none, with `state.now` as its last read."""
    live = ticket_stall.live(state.unwaited_since, state.now)
    return {n: DueEntry(e.since if (e := live.get(n)) is not None else state.now, state.now)
            for n in sorted(candidates(state))}


@memoized
def unwaited(state: State) -> Mapping[str, float]:
    """The tickets that wait on nothing, each with the time from which it
    has stood so: the candidates whose time in `times` is `AGAIN_SECONDS`
    or more before the read."""
    return {n: e.since for n, e in times(state).items() if state.now - e.since >= AGAIN_SECONDS}


def told(state: State, number: str, since: float) -> bool:
    """Whether a message to the coordinator done after `since` gives the
    part on ticket `number` (`OPENING`)."""
    opening = OPENING.format(number=number)
    return any(e.close is not None and e.close.time > since and opening in e.text
               for e in state.journal.sent(COORDINATOR))


def text(state: State, t: Ticket, since: float) -> str:
    """The part of the message to the coordinator on `t`, which has waited
    on nothing since `since`."""
    return OPENING.format(number=t.number) + "\n" + alerts.ticket_stall_text(state, t, since)


def step(state: State) -> Step | None:
    """The first step on the tickets of `unwaited`, in order of numbers:
    the one message that gives the coordinator `text` on each of them that
    `told` does not give, with `FIND_STEP`, then the step `ticket_step`
    gives on each from its time."""
    found = unwaited(state)
    untold = [n for n in sorted(found) if not told(state, n, found[n])]
    if untold:
        sent = Send(COORDINATOR,
                    "\n\n".join(text(state, state.tracker.tickets[n], found[n]) for n in untold)
                    + "\n\n" + alerts.FIND_STEP,
                    "unwaited " + " ".join(untold), max(found[n] for n in untold))
        if not repeated(sent, state):
            return sent
    for n in sorted(found):
        since = found[n]
        s = alerts.ticket_step(state, alerts.BugKind.UNWAITED, Domain.TICKET, n, since,
                        mctx("waits on nothing since {time}").format(time=utc_stamp(since)),
                        alerts.ticket_stall_text(state, state.tracker.tickets[n], since))
        if s is not None:
            return s
    return None
