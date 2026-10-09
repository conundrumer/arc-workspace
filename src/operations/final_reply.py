"""The operator's final reply: the calls that sent its text to the
coordinator (`final_sends`), the operator whose final reply carries what
reached an earlier one (`carrier`), and the lines the reply nests; with
the pattern of the report of an agent that sent its final reply by
SendMessage (`SENT_BY_MESSAGE`)."""

import re

from controlled_markdown import form, mctx
from operations.command_words import is_next
from operations.constants import COORDINATOR
from operations.handled import sends_to
from operations.printing import FINAL_REPLY, SENT, unfenced
from operations.roles import AGENT_ID
from operations.state import Call, State


SENT_BY_MESSAGE = re.compile(
    r"\A" + form(SENT, {"to": rf"(?:{re.escape(COORDINATOR)}|{AGENT_ID})"}) + r"\Z")
"""The whole text of `printing.SENT`, to the coordinator or to any agent."""


def final_sends(state: State, operator: str) -> list[Call]:
    """The SendMessage calls by which `operator` sent the coordinator the
    text of its final reply, in the order they were made."""
    return [c for c in sends_to(state, COORDINATOR) if c.operator == operator
            and unfenced(str(c.input.get("message", ""))).startswith(FINAL_REPLY + "\n")]


def final_replies(state: State, operator: str) -> list[float]:
    """The times of the calls of `next` that printed `operator` the
    messages of `final_sends`: for each, the last call of `next` before it."""
    nexts = [c.time for c in state.calls if c.operator == operator and c.tool == "Bash"
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


def nested(text: str) -> list[str]:
    """The lines of `text`, nested under an item of the final reply."""
    return [f"    {ln}".rstrip() for ln in text.strip().splitlines()]


def failure(c: Call) -> str:
    """The first line of the result of the failed call `c`."""
    reason = (c.result or "").strip().splitlines()
    return reason[0] if reason else mctx("no result text")
