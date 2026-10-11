"""The operator's final reply: the text of the message that sends it
(`final_text`, `sent_final_text`), whose form `printing.final_message`
gives, whether that text ends the operator for
its context (`for_context`), the calls that sent its text to its parent
(`final_sends`), the operator whose final reply carries what
reached an earlier one (`carrier`), and the lines the reply nests; with
the pattern of the report of an agent that sent its final reply by
SendMessage (`SENT_BY_MESSAGE`)."""

import re
from collections.abc import Iterable

from controlled_markdown import form, mctx
from operations.command_words import is_next
from operations.constants import COORDINATOR
from operations.handled import sends_in
from operations.printing import FINAL_REPLY, SENT, final_message, unfenced
from operations.roles import AGENT_ID
from operations.state import Call, State, Tool
from operations.steps import Reply, Send


FOR_CONTEXT = mctx("I ended for my context: launch a fresh operator with no lines, which "
                   "takes up from the state each line below that stands unfinished.")


def final_text(message: str) -> str | None:
    """The text of the final reply that `message` sends, or None where
    `message` sends none."""
    head, newline, text = message.partition("\n")
    return text if head == FINAL_REPLY and newline else None


def sent_final_text(call: Call) -> str | None:
    """The text of the final reply that the SendMessage call `call` sends,
    with or without the fence lines, or None where it sends none."""
    return final_text(unfenced(call.message))


def for_context(text: str) -> bool:
    """Whether the final reply whose text is `text` ends the operator for
    its context."""
    return text.split("\n", 1)[0] == FOR_CONTEXT


SENT_BY_MESSAGE = re.compile(
    r"\A" + form(SENT, {"to": rf"(?:{re.escape(COORDINATOR)}|{AGENT_ID})"}) + r"\Z")
"""The whole text of `printing.SENT`, to the coordinator or to any agent."""


def final_sends(state: State, operator: str) -> list[Call]:
    """The SendMessage calls by which `operator` sent its parent
    (`State.parents`) the text of its final reply, in the order they were
    made."""
    return final_sends_in(state.calls, operator, state.parents[operator])


def final_sends_in(calls: Iterable[Call], operator: str, to: str) -> list[Call]:
    """The SendMessage calls of `calls` by which `operator` sent `to` the
    text of its final reply, in the order they were made."""
    return [c for c in sends_in(calls, to) if c.operator == operator
            and sent_final_text(c) is not None]


def final_replies(state: State, operator: str) -> list[float]:
    """The times of the calls of `next` that printed `operator` the
    messages of `final_sends`: for each, the last call of `next` before it."""
    nexts = [c.time for c in state.calls if c.operator == operator and c.tool == Tool.BASH
             and is_next(str(c.input.get("command", "")), operator)]
    return [max((t for t in nexts if t < c.time), default=c.time)
            for c in final_sends(state, operator)]


def carrier(state: State, operator: str, time: float) -> str | None:
    """The operator whose final reply carries what reached `operator` at
    `time`: of `operator` and the operators launched after it, the one
    whose call that printed a final reply came first after `time`, with
    `me` counted as printing one now, or None where none did."""
    after = state.operators[state.operators.index(operator):]
    printed_at = [(t, o) for o in after for t in final_replies(state, o) if t > time]
    if state.me in after:
        printed_at.append((state.now, state.me))
    return min(printed_at)[1] if printed_at else None


def ending_step(to: str, text: str, sent: bool) -> Send | Reply:
    """The step of a final reply whose text is `text`, to the parent `to`:
    the message that sends `to` the text, or, where `sent`, as the
    message was already sent, the reply. A parent other than the
    coordinator is an operator launcher, whose command reads the message."""
    return Reply(to) if sent else Send(to, final_message(text), commanded=to != COORDINATOR)


def nested(text: str) -> list[str]:
    """The lines of `text`, nested under an item of the final reply."""
    return [f"    {ln}".rstrip() for ln in text.strip().splitlines()]


def failure(c: Call) -> str:
    """The first line of the result of the failed call `c`."""
    reason = (c.result or "").strip().splitlines()
    return reason[0] if reason else mctx("no result text")
