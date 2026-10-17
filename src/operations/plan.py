"""The operator's next step, in the order `order` gives, and its waits.

One operator carries the session's work at a time: an operator for which a
later one of the session runs ends at once, and the later one carries on
from the state, so two operators never act on one ticket. The coordinator's
lines, and the other agents' messages other than the alerts `alerts` acts
on for the operator that carries the work on, give steps only to the
operator they reached, so the work a line to an earlier operator left
unfinished reaches a later one only where the coordinator gives it again
(`passes.every`);
a `Decision:` line that rules a held step holds for every operator
(`directives`), and the items for the coordinator of a ticket analyst's
reply go to the final reply of the operator that carries that reply
(`final_reply.carrier`). An operator past its context bound ends at once
too, and asks its parent, the coordinator or an operator launcher, for a
fresh operator with no lines; the operator launched next takes up from the state each line
that the operators before it in a row that ended so received
(`taken_up`), and, once their work is no longer open, through
`taking.release`, the changes of the session and of the tickets the
coordinator gives it in a line, and of each ticket a chain of links
reaches from one of those.

Where no step is ready and a launch waits on the operator's agent
listing (`order.lacked`), the operator ends its turn, so that the resume
refreshes that listing. Otherwise, where no step is ready, and an agent
of an operator runs that is not
stuck, a ticket of the operators' waits on another holder whose work is
open and that is not stuck (`TranscriptsRead.stuck`), a ticket
file the read of the tracker left out may still be written
(`decisions.writing`), or the usage pace alone holds back an open
ticket (`taking.pace_held`), the agent runs
the command again, which blocks in the foreground first. Otherwise the
agent gives its final reply, after the message that sends its parent
its text (`standing.ending`), with each stuck agent or holder it waited on."""

from collections.abc import Mapping, Sequence

from controlled_markdown import mctx
from operations import decisions, monitor, triage, taking
from operations.state import Call, State
from ticketing.times import utc_stamp
from ticketing.vocabulary import Status
from operations.final_reply import FOR_CONTEXT, final_sends_in, for_context, live_holder, sent_final_text
from operations.standing import ending, final, holding, reply_lines
from operations.order import EARLY, LATE, first, lacked, listing_wait, monitor_step
from operations.steps import EndTurn, ListingHold, Poll, Step

GIVEN_AGAIN = mctx("a line below that stands unfinished reaches it only where it is given to it "
                   "again")


def elsewhere(state: State) -> list[str]:
    """The tickets of the operators' scope that another live holder
    (`live_holder`) of the session (`State.session_holders`) holds."""
    return [n for n in sorted(taking.scope(state))
            if (t := state.tracker.tickets.get(n)) is not None and t.status is Status.ASSIGNED
            and t.holder not in (None, state.me) and t.holder in state.session_holders
            and live_holder(state, t.holder)]


def unknown_line(line: str) -> str:
    """The line of a final reply that gives the `monitor.undecided` line
    `line`."""
    return f"- {line}"


def next_step(state: State, watch: monitor.MonitorState) -> Step:
    """The operator's next step, where `watch` is the state the monitor's
    steps read. Each reply gives, after its lines, each line
    `monitor.undecided` gives."""
    unknown = [unknown_line(line) for line in dict.fromkeys(monitor.undecided(watch))]
    mine = state.operators.index(state.me) if state.me in state.operators else -1
    later = [o for o in state.operators[mine + 1:] if o in state.open_operators]
    if later:
        return ending(state,
                      mctx("Operator {operator} carries the work on, from the state; {given}.").format(
                          operator=later[-1], given=GIVEN_AGAIN)
                      + "\n" + "\n".join([*reply_lines(state, holding(state)), *unknown]))
    s = first(state, *EARLY)
    if s is not None:
        return s
    if state.past_bound:
        return ending(state,
                      FOR_CONTEXT + "\n" + "\n".join([*reply_lines(state, holding(state)), *unknown]))
    s = first(state, lambda st: monitor_step(st, watch), *LATE)
    if s is not None:
        return s
    held = lacked(state)
    if held is not None:
        return EndTurn(ListingHold(held, listing_wait(state, held)))
    pace = taking.pace_held(state, [*triage.unsettled_open(state),
                                    *(t.number for t in taking.ready(state)
                                      if not taking.taken_before(t))])
    stuck = state.transcripts.stuck
    waits = [a.agent_id for a in state.transcripts.agents if a.pending or a.agent_id in state.transcripts.quiet]
    waits += [h for n in elsewhere(state) if (h := state.tracker.tickets[n].holder) is not None]
    if (pace is not None or any(w is None or w not in stuck for w in waits)
            or any(decisions.writing(state, u) for u in state.tracker.unread)):
        return Poll(pace)
    quiet = [mctx("- Stopped waiting on {agent}: no progress since {time}.").format(
        agent=w, time=utc_stamp(stuck[w].since)) for w in dict.fromkeys(waits) if w is not None]
    return ending(state, "\n".join([final(state, holding(state)), *quiet, *unknown]))


def taken_up(me: str, operators: Sequence[str], calls: Sequence[Call],
             parents: Mapping[str, str]) -> frozenset[str]:
    """The operators of `operators` launched right before `me`, in a row,
    each of which `next` printed the final reply `FOR_CONTEXT`, as their
    `calls` to their `parents` give it."""
    mine = operators.index(me) if me in operators else 0
    out: set[str] = set()
    for o in reversed(operators[:mine]):
        if not any(for_context(sent_final_text(c) or "")
                   for c in final_sends_in(calls, o, parents[o])):
            break
        out.add(o)
    return frozenset(out)
