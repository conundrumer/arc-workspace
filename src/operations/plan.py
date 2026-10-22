"""The operator's next step, in the order `order` gives, and its waits.

One operator does the session's work at a time: an operator for which a
later one of the session runs, and has not ended (`final_reply.ended`)
or takes up its lines (`taken_up`), ends at once, and the later one
continues from the state, so two operators never act on one ticket. Of
an operator whose final reply hands its lines to a later one and that
later one, one alone continues those lines (`final_reply.takes_up`).
The coordinator's lines, and the other agents' messages other than the
alerts `alerts` acts on for the operator that continues the work, give steps only to the
operator they reached or to one that takes them up (`taken_up`);
an `Op decision:` line that rules a held step holds for every operator
(`directives`), and the items for the coordinator of a ticket analyst's
reply go to the final reply of the operator that gives that reply
(`final_reply.carrier`). An operator past its context bound ends at once
too, and asks its parent, the coordinator or an operator launcher, for a
fresh operator with no lines. The operator launched next takes up from the state each line
that the operators before it in a row, each ended for its context or for a later operator,
received (`taken_up`), and, once their work is no longer open, through
`taking.release`, the changes of the session and of the tickets the
coordinator gives it in a line, and of each ticket a chain of links
reaches from one of those. An operator also takes up each line that an
operator that ended for it by name received, with the lines that
operator took up (`taken_up`).

Where no step is ready and a launch waits on the operator's agent
listing (`order.lacked`), the operator ends its turn, so that the resume
refreshes that listing. Otherwise, where no step is ready, and an agent
of an operator runs that is not
stuck, a ticket of the operators' waits on another holder whose work is
open and that is not stuck (`TranscriptsRead.stuck`), an operator
launched before it in the session has open work and is not stuck
(`earlier_open`), so that the agent takes up that operator's lines once
that operator has given its final reply (`taken_up`), a ticket
file the read of the tracker left out may still be written
(`decisions.writing`), the usage pace alone holds back an open
ticket (`admission.pace_held`), the pace or its cap holds a step (`order.pace_held_step`), or
a step waits after the harness refused it at its limit of concurrent
subagents (`journal.backing_off`), the agent runs the command again, which blocks in the foreground first,
until its calls in a row have found no step ready for `WAIT_SECONDS_IDLE`: then, where an
agent it launched is pending, it waits with its turn ended (`steps.Wait`), and otherwise it
gives its final reply for a wait (`final_reply.FOR_WAIT`), whose lines a fresh operator takes
up. Otherwise the
agent gives its final reply, after the message that sends its parent
its text (`standing.ending`), with each stuck agent or holder it waited on."""

from collections.abc import Iterable, Mapping, Sequence

from controlled_markdown import mctx
from operations import admission, change_take, decisions, monitor, triage, taking
from operations.state import Call, State, Stuck
from ticketing.times import utc_stamp
from ticketing.vocabulary import Status
from operations.constants import WAIT_SECONDS_IDLE
from operations.journal import backing_off, next_call
from operations.printing import printed_idle
from operations.final_reply import (FOR_CONTEXT, FOR_LATER, FOR_WAIT, ended, hands_over, hands_to,
                                    live_holder, own_calls, sent_final_text, split_at,
                                    takes_up)
from operations.standing import ending, final, holding, reply_lines
from operations.order import EARLY, LATE, first, lacked, listing_wait, monitor_step, pace_held_step
from operations.steps import EndTurn, ListingHold, Poll, Step, Wait


def elsewhere(state: State) -> list[str]:
    """The tickets of the operators' purview (`taking.purview`) that
    another live holder (`live_holder`) of the session
    (`State.session_holders`) holds."""
    return [n for n in sorted(taking.purview(state))
            if (t := state.tracker.tickets.get(n)) is not None and t.status is Status.ASSIGNED
            and t.holder not in (None, state.me) and t.holder in state.session_holders
            and live_holder(state, t.holder)]


def earlier_open(state: State) -> list[str]:
    """The operators of `State.open_operators` launched before `me`, in
    the order of their launch."""
    return [o for o in split_at(state.operators, state.me)[0] if o in state.open_operators]


def unknown_line(line: str) -> str:
    """The line of a final reply that gives the `monitor.undecided` line
    `line`."""
    return f"- {line}"


def unknown_lines(watch: monitor.MonitorState) -> list[str]:
    """The lines of a final reply that give each line `monitor.undecided`
    gives."""
    return [unknown_line(line) for line in dict.fromkeys(monitor.undecided(watch))]


def next_step(state: State, watch: monitor.MonitorState, waiting: bool = False) -> Step:
    """The operator's next step, where `watch` is the state the monitor's
    steps read and `waiting` is whether a call of the command's `wait` by
    `me` runs: the step `ready_step` gives, other than where it is `Poll`
    and the calls of `next` by `me` in a row have found no step ready for
    `WAIT_SECONDS_IDLE` (`idle_since`). There, where an agent `me`
    launched is pending or `waiting` holds, the step is `Wait`, with the
    call where `waiting` does not hold, and otherwise the final reply
    for a wait (`FOR_WAIT`). Each reply gives, after its lines, each line
    `monitor.undecided` gives."""
    step = ready_step(state, watch)
    since = idle_since(state.transcripts.calls, state.me)
    if not isinstance(step, Poll) or since is None or state.now - since < WAIT_SECONDS_IDLE:
        return step
    if waiting or any(a.pending for a in state.transcripts.agents if a.operator == state.me):
        return Wait(state.me, call=not waiting)
    return ending(state, FOR_WAIT + "\n" + "\n".join([*reply_lines(state, holding(state)),
                                                      *unknown_lines(watch)]))


def idle_since(calls: Iterable[Call], me: str) -> float | None:
    """The time of the first of the calls of `next` by `me` with a result,
    in a row back from the last, whose results print that nothing is
    ready (`printing.printed_idle`), or None where the last result prints
    a step."""
    since = None
    for c in sorted((c for c in calls if next_call(c, me) and c.result is not None),
                    key=lambda c: c.time, reverse=True):
        if not printed_idle(c.result or ""):
            break
        since = c.time
    return since


def stopped_waiting(agent: str, s: Stuck) -> str:
    """The line of the final reply on the agent `agent`, stuck as `s` gives,
    that the operator stopped waiting on: the diagnostic of a held Codex
    attempt whose turn is unknown, where `s` has one, and otherwise the
    transcript condition."""
    if s.unknown is not None:
        return mctx("- Stopped waiting on {agent}, which stays held with no write to its "
                    "transcripts or its Codex rollout since {time}: {diagnostic}").format(
            agent=agent, time=utc_stamp(s.since), diagnostic=s.unknown)
    return mctx("- Stopped waiting on {agent}: no new transcript activity or unchanged Bash "
                "results since {time}.").format(agent=agent, time=utc_stamp(s.since))


def ready_step(state: State, watch: monitor.MonitorState) -> Step:
    """The operator's next step as the module docstring gives it, where
    `watch` is the state the monitor's steps read, with no wait for
    nothing ready (`next_step`). Each reply gives, after its lines, each
    line `monitor.undecided` gives."""
    unknown = unknown_lines(watch)
    later = [o for o in split_at(state.operators, state.me)[1] if o in state.open_operators
             and (not ended(state, o) or state.me in taken_up(o, state.operators,
                                                             state.transcripts.calls,
                                                             state.parents))]
    if later:
        return ending(state,
                      FOR_LATER.format(operator=later[-1])
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
    pace = admission.pace_held(state, [*triage.unsettled_open(state),
                                    *(t.number for t in change_take.ready(state))])
    if pace is None:
        pace = pace_held_step(state)
    stuck = state.transcripts.stuck
    waits = [a.agent_id for a in state.transcripts.agents if a.pending or a.agent_id in state.transcripts.quiet]
    waits += [h for n in elsewhere(state) if (h := state.tracker.tickets[n].holder) is not None]
    waits += earlier_open(state)
    if (pace is not None or any(w is None or w not in stuck for w in waits)
            or any(decisions.writing(state, u) for u in state.tracker.unread)
            or backing_off(state.journal, state.now)):
        return Poll(pace)
    quiet = [stopped_waiting(w, stuck[w]) for w in dict.fromkeys(waits) if w is not None]
    return ending(state, "\n".join([final(state, holding(state)), *quiet, *unknown]))


def taken_up(me: str, operators: Sequence[str], calls: Sequence[Call],
             parents: Mapping[str, str]) -> frozenset[str]:
    """The operators of `operators` before `me` whose lines `me` takes up,
    by the last final send of each to its parent, of its `calls` to its
    `parents`, as a final reply sent again after a later message stands in
    place of the one before it: those launched right before `me`, in a row,
    each of whose last final send hands its lines over (`hands_over`), each
    whose last final send hands its lines to `me` by name (`hands_to`), and
    those each of these takes up, whose lines its reply gives; of these,
    only those whose lines the operator they hand them to takes up
    (`takes_up`), and not those that continue them themselves."""
    before = split_at(operators, me)[0]
    own = own_calls(calls, parents)
    texts = {o: sent_final_text(sends[-1]) or "" for o in before
             if (sends := own[o].finals)}
    ups: dict[str, frozenset[str]] = {}
    for i, op in enumerate([*before, me]):
        row: list[str] = []
        for o in reversed(operators[:i]):
            if o not in texts or not hands_over(texts[o]) or not takes_up(own, o, op):
                break
            row.append(o)
        named = [o for o in operators[:i]
                 if o in texts and hands_to(texts[o], op) and takes_up(own, o, op)]
        ups[op] = frozenset({*row, *named}.union(*(ups[o] for o in [*row, *named])))
    return ups[me]
