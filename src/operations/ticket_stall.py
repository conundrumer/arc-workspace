"""The tickets that stall, and the move to `tickets/draft/` of a change
that waits on a ticket that holds it up.

A ticket of `taking.purview` is stalled (`stalled`) where an operator's step
is due on it (`due`) and `TICKET_STUCK_SECONDS` have passed since the later of its
last progress and the time from which a step has been due on it
(`due_times`), whatever the cause that held it. A step is due on it by an
exit of `tracker.exits` that an operator's step makes, read by the
function that step selects its work by (`selection`); a ticket whose only
exits are steps of no operator, or that such a function leaves out, waits
by design and is not due, and so does a ticket whose step the usage pace
holds (`start_holds.pace_holds`). The party such a ticket waits on is the
one that function names where it leaves it out (`party`), and `unwaited`
watches such a ticket whose party does not stand. A ticket
that a live holder other than this operator holds waits on that
holder's work, a step of no operator, and is not due; the stuck check
watches a holder of the session (`plan.elsewhere`,
`TranscriptsRead.stuck`), and a holder outside it is watched by its own
session. Its progress is a line of its log other than a
take or a release, the first take after such progress, the launch of an
agent of it, a report of such an agent, and, for a change, its merge onto
`master`; an agent of it that is pending and not quiet is progress too,
and a ticket with one is not stalled.

The time from which a step has been due on a ticket is the time of the
first read of the state, by an operator of the session for a step, of
those since which each such read found the step due on it, as
`State.due_since` records it with the time of the last read that found
the step due. A read that finds a ticket of its `taking.purview` not due
drops that time, and keeps the times of tickets outside it; at each read,
in its purview or not, a ticket whose last read that found it due is
`TICKET_STUCK_SECONDS` or more before the read at hand loses its time
(`live_entries`); a ticket that `State.due_since` does not hold is due
from the read at hand.

A change that waits for a ticket that holds it up (`holding`), one under
`tickets/blocked/` or one that has been stalled for `STUCK_SECONDS`, moves to `tickets/draft/` with
a line whose note is `taking.STALL_FINDING` on that ticket, once after the
time from which that ticket holds it up (`stall`)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import assert_never

from operations import (change_take, changes, drafts, lineage, merging, start_holds, taking, triage,
                        waits)
from operations.change_budget import TAKEN
from operations.constants import stuck_reached, ticket_stuck_reached
from operations.final_reply import live_holder
from operations.log_commands import log
from operations.parties import Hold, Holder, Party
from operations.state import (RELEASED_LINE, Agent, DueEntry, State, Ticket, kept_across_reads, memoized,
                              memoized_by_transcripts)
from operations.handled import held_aside
from operations.steps import Bash, NoStep, Step
from operations.tracker import exits
from ticketing.exits import Exit
from ticketing.times import utc_stamp
from ticketing.vocabulary import Kind, Status


def held_by_other_live_holder(state: State, t: Ticket) -> bool:
    return (t.holder is not None and t.holder != state.me
            and live_holder(state, t.holder))


@memoized
def selection(state: State, e: Exit) -> set[str]:
    """The tickets on which the step that makes `e` is due, as the function
    that step selects its work by gives them, less those whose step the
    usage pace holds (`start_holds.pace_holds`), or none where no operator's
    step makes `e`."""
    match e:
        case Exit.RELEASE:
            return {n for n in assigned(state)
                    if (h := state.tracker.tickets[n].holder) is None or not live_holder(state, h)}
        case Exit.HOLDER:
            return {n for n in assigned(state) if not start_holds.pace_holds(
                state, lambda: change_step(state, state.tracker.tickets[n]))}
        case Exit.TAKE:
            return {t.number for t in change_take.reach(state)}
        case Exit.TICKET_REVIEW:
            return {n for n in drafts.due(state) if not review_held(state, n)}
        case Exit.TICKET_ANALYST:
            return set(triage.selected(state))
        case (Exit.MERGE | Exit.CHANGE_ANALYST | Exit.COORDINATOR_MOVE | Exit.COORDINATOR_LINE
              | Exit.MERGE_LINE | Exit.CHANGE_CLOSE | Exit.SWEEP):
            return set()
        case _:
            assert_never(e)


def party(state: State, e: Exit, t: Ticket) -> Party | None:
    """The party that `t`, which `selection` of `e` leaves out, waits on,
    as the function that step selects its work by names it, or None where
    it names none or no operator's step makes `e`: the holder of a ticket
    the release or the holder's step leaves out, or the usage pace where
    it holds the holder's step (`HOLDER`); the party of
    `change_take.left` (`TAKE`); the usage pace where it holds the review
    of a draft on which a step is due (`review_held`), and otherwise the
    agents of `drafts.writing` on a draft given to the operators
    (`TICKET_REVIEW`); and that of `triage.party` (`TICKET_ANALYST`)."""
    match e:
        case Exit.RELEASE:
            return holder(t)
        case Exit.HOLDER:
            return (Hold.PACE if t.number in assigned(state) and start_holds.pace_holds(
                state, lambda: change_step(state, t)) else holder(t))
        case Exit.TAKE:
            return change_take.left(state).get(t.number)
        case Exit.TICKET_REVIEW:
            if t.number in drafts.due(state) and review_held(state, t.number):
                return Hold.PACE
            return drafts.writing(state, t) if t.number in drafts.draft_numbers(state) else None
        case Exit.TICKET_ANALYST:
            return triage.party(state, t.number)
        case (Exit.MERGE | Exit.CHANGE_ANALYST | Exit.COORDINATOR_MOVE | Exit.COORDINATOR_LINE
              | Exit.MERGE_LINE | Exit.CHANGE_CLOSE | Exit.SWEEP):
            return None
        case _:
            assert_never(e)


def holder(t: Ticket) -> Holder | None:
    """The holder of `t`, where it has one."""
    return None if t.holder is None else Holder(t.holder)


def change_step(state: State, t: Ticket) -> Step | None:
    """The next step on a change held by this operator, or None where it
    has none (`steps.NoStep`) or is not held."""
    if not changes.holds(t, state.me):
        return None
    step = changes.next_step(state, t)
    return None if isinstance(step, NoStep) else step


def review_held(state: State, number: str) -> bool:
    """Whether the Claude pace holds a draft's concrete review step."""
    return start_holds.pace_holds(
        state, lambda: drafts.review_step(state, state.tracker.tickets[number]))


@memoized
def assigned(state: State) -> frozenset[str]:
    """The tickets under `tickets/assigned/` that no live holder other
    than this operator holds (`held_by_other_live_holder`)."""
    return frozenset(n for n, t in state.tracker.tickets.items()
                     if t.status is Status.ASSIGNED and not held_by_other_live_holder(state, t))


def agents_of(state: State, number: str) -> tuple[Agent, ...]:
    return agents_by_ticket(state).get(number, ())


@memoized_by_transcripts
def agents_by_ticket(state: State) -> Mapping[str, tuple[Agent, ...]]:
    """The agents of each ticket number their subject gives
    (`lineage.tickets`), in the order of `TranscriptsRead.agents`."""
    return held_agents_by_ticket((), state.transcripts.agents)


@kept_across_reads
def held_agents_by_ticket(agents: tuple[Agent, ...]) -> Mapping[str, tuple[Agent, ...]]:
    out: dict[str, list[Agent]] = {}
    for a in agents:
        for n in dict.fromkeys(lineage.tickets(a.role, a.subject)):
            out.setdefault(n, []).append(a)
    return {n: tuple(agents) for n, agents in out.items()}


def progress(state: State, t: Ticket) -> float | None:
    """The time of `t`'s last progress, or None where an agent of it is
    at work."""
    agents = agents_of(state, t.number)
    if any(a.pending and a.agent_id not in state.transcripts.quiet for a in agents):
        return None
    merge = merging.merge_commit(state, t) if t.kind is Kind.CHANGE else None
    completion = merging.empty_completion(state, t) if t.kind is Kind.CHANGE else None
    last: float = max([t.filed,
                       *([completion.time] if completion is not None else []),
                       *([merge.time] if merge is not None else []),
                       *(ln.time for ln in t.log
                         if TAKEN.fullmatch(ln.note) is None and RELEASED_LINE.fullmatch(ln.note) is None),
                       *(a.launched for a in agents),
                       *(r.time for a in agents for r in a.reports)])
    return next((ln.time for ln in t.log
                 if ln.time > last and TAKEN.fullmatch(ln.note) is not None), last)


@memoized
def due(state: State) -> frozenset[str]:
    """The tickets of `taking.purview` on which an operator's step is due."""
    selections: dict[Exit, set[str]] = {}
    out: set[str] = set()
    for n in sorted(taking.purview(state)):
        t = state.tracker.tickets.get(n)
        if t is None:
            continue
        for e in sorted(exits(state, t).by):
            if e not in selections:
                selections[e] = selection(state, e)
            if n in selections[e]:
                out.add(n)
                break
    return frozenset(out)


def live_entries(state: State) -> dict[str, DueEntry]:
    """The entries of `State.due_since` whose last read that found the
    step due has not reached `TICKET_STUCK_SECONDS` at `state.now`."""
    return live(state.due_since, state.now)


def live(record: Mapping[str, DueEntry], now: float) -> dict[str, DueEntry]:
    """The entries of `record` whose last read has not reached
    `TICKET_STUCK_SECONDS` at `now`."""
    return {n: e for n, e in record.items() if not ticket_stuck_reached(e.last, now)}


def due_times(state: State) -> dict[str, DueEntry]:
    """The record of the times from which a step has been due, after the
    read that gave `state`: for each ticket of `due`, its time in
    `live_entries`, or `state.now` where that holds none, with `state.now`
    as its last read; and the entries of `live_entries` for tickets
    outside `taking.purview`, as they are."""
    purview = taking.purview(state)
    live = live_entries(state)
    return {**{n: e for n, e in live.items() if n not in purview},
            **{n: DueEntry(e.since if (e := live.get(n)) is not None else state.now, state.now)
               for n in sorted(due(state))}}


@memoized
def stalled(state: State) -> Mapping[str, float]:
    """The stalled tickets, each with the later of the time of its last
    progress and the time from which a step has been due on it: an
    operator's step is due on each."""
    since = due_times(state)
    out: dict[str, float] = {}
    for n in sorted(due(state)):
        if (last := progress(state, state.tracker.tickets[n])) is not None:
            start = max(last, since[n].since)
            if ticket_stuck_reached(start, state.now):
                out[n] = start
    return out


@dataclass(frozen=True)
class Acting:
    """How `stall` and the message of `alerts.stuck_waits` act on the
    ticket `number`, on the paths of a waiting change, whose mark is
    `mark`, where `entry` is whether it is an open `depends-on` entry of
    that change."""
    state: State
    number: str
    mark: "waits.Mark | None"
    entry: bool

    @property
    def stall(self) -> tuple[float, str] | None:
        """The time from which the ticket holds up the change, with the
        reason, where `stall` acts on it: an entry whose mark is
        `waits.OnUser` or `waits.NoStep`, from that mark's time."""
        if not self.entry:
            return None
        match self.mark:
            case waits.OnUser(since):
                return since, waits.ON_USER
            case waits.NoStep(since):
                return since, waits.NO_STEP.format(time=utc_stamp(since))
            case _:
                return None

    @property
    def told(self) -> bool:
        """Whether the mark makes `next` send the coordinator the paths of
        the change, as `--help alerts` of `operate.py` gives it."""
        match self.mark:
            case waits.OnCycle() | waits.Unwaited():
                return True
            case waits.OnUser():
                return not self.entry or waits.cycle(self.state, self.number) is not None
            case _:
                return False


def holding(state: State, u: Ticket, stalls: Mapping[str, float]) -> tuple[float, str] | None:
    """The time from which `u`, an entry of the `depends-on` of a waiting
    change, holds up that change, with the reason, where it does
    (`Acting.stall`), with `stalls` as `stalled` gives them."""
    return Acting(state, u.number, waits.mark(state, u.number, stalls), True).stall


def stall(state: State) -> Step | None:
    """The move to `tickets/draft/` of a change that `waiting()` gives that
    waits for a ticket that `holding` gives, where no line of its log
    since the time `holding` gives gives `taking.STALL_FINDING` on it. A
    ticket holds up a change only once it has stalled for `STUCK_SECONDS`, not
    for `TICKET_STUCK_SECONDS`."""
    stalls = {n: t for n, t in stalled(state).items() if stuck_reached(t, state.now)}
    for n, deps in change_take.waiting(state):
        t = state.tracker.tickets[n]
        for d in deps:
            u = state.tracker.tickets.get(d)
            held_up = None if u is None else holding(state, u, stalls)
            if held_up is None:
                continue
            since, reason = held_up
            if not any(ln.time >= since and (m := taking.STALLED.match(ln.note)) is not None
                       and m["number"] == d for ln in t.log):
                step = Bash(log(n, Status.DRAFT, t.status,
                                taking.STALL_FINDING.format(number=d, reason=reason), state.me),
                            f"{n} stalled on {d}", occasion=str(since))
                if not held_aside(state, step):
                    return step
    return None
