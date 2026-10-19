"""The operator's final reply: the text of the message that sends it
(`final_text`, `sent_final_text`), whose form `printing.final_message`
gives, whether that text ends the operator for
its context (`for_context`) or hands its lines to the operator launched
after it (`hands_over`) or to one operator by name (`hands_to`), the calls that sent its text to its parent
(`final_sends`), the calls of each operator (`OwnCalls`), whether an operator has ended (`ended`), which of two
operators continues the lines one hands the other (`takes_up`), whether a holder
of a change is live (`live_holder`), the operators launched before and
after one (`split_at`),
the operator whose final reply gives what
reached an earlier one (`carrier`), the operator whose launch an agent is or
stands in (`session_operator`), and the lines the reply nests.
`ended_at`, `takes_up` and `carrier` read the calls of
`next` by `handled.next_call`."""

import re
from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from controlled_markdown import form, mctx
from operations.constants import COORDINATOR
from operations.handled import sends_in
from operations.journal import next_call
from operations.printing import FINAL_REPLY, final_message, unfenced
from operations.state import Agent, Call, State, Tool, kept_across_reads, memoized
from operations.steps import Reply, Send


FOR_CONTEXT = mctx("I ended for my context: launch a fresh operator with no lines, which "
                   "takes up from the state each line below that stands unfinished.")

FOR_LATER = mctx("Operator {operator} continues the work, and takes up from the state each "
                 "line below that stands unfinished.")
"""The first line of the final reply of an operator that ends because a
later operator of the session is open."""


def final_text(message: str) -> str | None:
    """The text of the final reply that `message`, with or without the
    fence lines, sends, or None where `message` sends none."""
    head, newline, text = unfenced(message).partition("\n")
    return text if head == FINAL_REPLY and newline else None


def sent_final_text(call: Call) -> str | None:
    return final_text(call.message)


def first_line(text: str) -> str:
    return text.split("\n", 1)[0]


def for_context(text: str) -> bool:
    """Whether the final reply whose text is `text` ends the operator for
    its context."""
    return first_line(text) == FOR_CONTEXT


def hands_over(text: str) -> bool:
    """Whether the final reply whose text is `text` hands the operator's
    lines to the operator launched after it: its first line is
    `FOR_CONTEXT` or has the form of `FOR_LATER`."""
    return for_context(text) or re.fullmatch(form(FOR_LATER, {"operator": r"\S+"}),
                                              first_line(text)) is not None


def hands_to(text: str, operator: str) -> bool:
    """Whether the final reply whose text is `text` hands the operator's
    lines to `operator` by name: its first line is `FOR_LATER` for
    `operator`."""
    return first_line(text) == FOR_LATER.format(operator=operator)


def final_sends(state: State, operator: str) -> list[Call]:
    """The SendMessage calls by which `operator` sent its parent
    (`State.parents`) the text of its final reply, in the order they were
    made."""
    return list(operator_calls(state)[operator].finals)


@dataclass(frozen=True)
class OwnCalls:
    """The calls of one operator (`calls`), the times of its calls of
    `next`, in order (`nexts`), and `final_sends_in` of its calls to its
    parent (`finals`)."""
    calls: tuple[Call, ...]
    nexts: tuple[float, ...]
    finals: tuple[Call, ...]


def own_calls(calls: Iterable[Call], parents: Mapping[str, str]) -> dict[str, OwnCalls]:
    """The `OwnCalls` of each operator of `parents`, each to the parent
    `parents` gives it, from `calls`."""
    mine: dict[str, list[Call]] = {o: [] for o in parents}
    for c in calls:
        if c.operator in mine:
            mine[c.operator].append(c)
    return {o: OwnCalls(tuple(own), tuple(sorted(c.time for c in own if next_call(c, o))),
                        tuple(final_sends_in(own, o, parents[o])))
            for o, own in mine.items()}


@memoized
def operator_calls(state: State) -> dict[str, OwnCalls]:
    """`own_calls` of the calls of `state` to `State.parents`."""
    return held_own_calls((), state.transcripts.calls, state.parents)


held_own_calls = kept_across_reads(own_calls)


def final_sends_in(calls: Iterable[Call], operator: str, to: str) -> list[Call]:
    """The SendMessage calls of `calls` by which `operator` sent `to` the
    text of its final reply, in the order they were made."""
    return [c for c in sends_in(calls, to) if c.operator == operator
            and sent_final_text(c) is not None]


def split_at(operators: Sequence[str], me: str) -> tuple[Sequence[str], Sequence[str]]:
    """The operators of `operators` launched before `me` and those launched
    after it. Raises `ValueError` where `me` is not among `operators`."""
    mine = operators.index(me)
    return operators[:mine], operators[mine + 1:]


def ended(state: State, operator: str) -> bool:
    """Whether `operator` has `ended_at` now."""
    return ended_at(operator_calls(state)[operator], operator, float("inf"))


def ended_at(own: OwnCalls, operator: str, at: float) -> bool:
    """Whether, of the calls `own` of `operator` made before `at`,
    `operator` has sent its parent its final reply and made only calls of
    `next` and SubagentHandback since; a SubagentHandback call ends the run
    and counts as no work. The final send is itself a SendMessage call, so
    only the calls after it are read."""
    sends = [c for c in own.finals if c.time < at]
    if not sends:
        return False
    last = sends[-1].time
    return all(next_call(c, operator) or c.tool == Tool.SUBAGENT_HANDBACK
               for c in own.calls if last < c.time < at)


def takes_up(own: Mapping[str, OwnCalls], earlier: str, later: str) -> bool:
    """Whether `later` takes up the lines that the last final send of the
    operator `earlier`, launched before it, hands it (`hands_to`, or
    `hands_over` in a row), where `own` gives the calls of each. Of the
    two, the one whose call of `next` after that send came first continues
    those lines: `earlier` only where its call came first and `later`
    had `ended_at` that call."""
    sent = own[earlier].finals[-1].time
    first_earlier = first_next(own[earlier], sent)
    first_later = first_next(own[later], sent)
    if first_earlier is None or (first_later is not None and first_later < first_earlier):
        return True
    return not ended_at(own[later], later, first_earlier)


def first_next(own: OwnCalls, after: float) -> float | None:
    """The time of the first call of `next` of `own` after `after`, or None
    where it made none."""
    i = bisect_right(own.nexts, after)
    return own.nexts[i] if i < len(own.nexts) else None


def live_holder(state: State, holder: str) -> bool:
    """Whether `holder` holds its changes live: it stands in
    `open_holders`, and it is not an operator launched before `me` that
    has `ended`. An earlier operator whose step is in flight when `me`
    starts has made no final send yet, and holds its changes until its
    next call of `next` ends it."""
    if holder not in state.open_holders:
        return False
    return holder not in split_at(state.operators, state.me)[0] or not ended(state, holder)


@memoized
def final_replies(state: State, operator: str) -> list[float]:
    """The times of the calls of `next` that printed `operator` the
    messages of `final_sends`: for each, the last call of `next` before it."""
    own = operator_calls(state)[operator]
    return [own.nexts[i - 1] if (i := bisect_left(own.nexts, c.time)) else c.time
            for c in own.finals]


def replies_by_operator(state: State) -> dict[str, list[float]]:
    """`final_replies` of each operator of `state.operators`."""
    return {o: final_replies(state, o) for o in state.operators}


def carrier(state: State, operator: str, time: float,
            replies: Mapping[str, list[float]]) -> str | None:
    """The operator whose final reply gives what reached `operator` at
    `time`: of `operator` and the operators launched after it, the one
    whose call that printed a final reply came first after `time`, by
    `replies`, which `replies_by_operator` gives, with `me` counted as
    printing one now, or None where none did. `operator` is an operator
    of `state.operators`; `session_operator` gives it for an agent."""
    after = state.operators[state.operators.index(operator):]
    printed_at = [(t, o) for o in after for t in replies[o] if t > time]
    if state.me in after:
        printed_at.append((state.now, state.me))
    return min(printed_at)[1] if printed_at else None


def session_operator(state: State, a: Agent) -> str | None:
    """The operator of `state.operators` whose launch `a` is or stands in:
    `a.operator` where it is one, else the `operator` of the agent of
    `state.transcripts.agents` whose id is `a.operator`, the editor that
    launched `a`, where that one is, or None where neither is."""
    if a.operator in state.operators:
        return a.operator
    return next((e.operator for e in state.transcripts.agents
                 if e.agent_id == a.operator and e.operator in state.operators), None)


def ending_step(to: str, text: str, since: float, sent: bool) -> Send | Reply:
    """The step of a final reply whose text is `text`, to the parent `to`:
    the message that sends `to` the text after `since`, or, where `sent`,
    as that message was already sent, the reply. A parent other than the
    coordinator is an operator launcher, whose command reads the message."""
    return Reply(to) if sent else Send(to, final_message(text), FINAL_REPLY, since,
                                       commanded=to != COORDINATOR)


def nested(text: str) -> list[str]:
    """The lines of `text`, nested under an item of the final reply."""
    return [f"    {ln}".rstrip() for ln in text.strip().splitlines()]


def failure(c: Call) -> str:
    """The first line of the result of the failed call `c`."""
    reason = (c.result or "").strip().splitlines()
    return reason[0] if reason else mctx("no result text")
