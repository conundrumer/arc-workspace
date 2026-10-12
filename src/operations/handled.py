"""Whether an operator already made or handled a step, read from the
operators' calls in the state.

Which call makes a step the command printed is as `operate.py --help next`
gives it, and `made` reads the call made right after `next`. A message
counts as made as well by each SendMessage call that holds the printed
message. `next_call` tells a call of `next` by an operator."""

import re
from collections.abc import Callable, Iterable
from functools import cache

from controlled_markdown import form
from operations import messages
from operations.command_words import is_next, only_command
from operations.constants import COORDINATOR
from operations.printing import KEY_LINE, bash_text, opening, send_opening, unfenced
from operations.roles import Purpose
from operations.state import Agent, Call, Made, State, Tool
from operations.steps import STEP_KEY, UNDECIDED, Bash, Send, Step, Undecided, decision_key, key


def next_call(c: Call, operator: str) -> bool:
    """Whether `c` is a call of `next` by `operator`."""
    return (c.operator == operator and c.tool == Tool.BASH
            and is_next(str(c.input.get("command", "")), operator))


def decided_by(state: State, step: Undecided) -> list[Agent]:
    """The ticket analysts of any operator of the session launched on
    `step`, in the order of their launch."""
    k = decision_key(step.what)
    return [a for a, purpose, keys in state.analysts() if purpose is Purpose.STEP and keys == [k]]


def repeated(step: Step, state: State) -> bool:
    """Whether `step` is a message an operator already sent, or an
    undecided step that an operator already handled: a ticket analyst was
    launched on it, or an operator gave it to the coordinator, as
    `steps.UNDECIDED` and its `what`, or in a message that holds each of its
    `given`. Its procedure then waits on the answer."""
    match step:
        case Undecided(what, given):
            return bool(decided_by(state, step)) or sent(state, COORDINATOR,
                                                       f"{UNDECIDED} {what}") or (
                bool(given) and any(all(g in c.message for g in given)
                                    for c in sends_to(state, COORDINATOR)))
        case Send():
            return bool(sendings(step, state))
        case _:
            return False


def answered(step: Send, state: State) -> bool:
    """Whether an operator already sent `step`, as `repeated` reads it,
    and its recipient does not run and reported after its latest
    sending."""
    times = sendings(step, state)
    if not times:
        return False
    of = [a for a in state.agents if a.agent_id == step.to]
    return not any(a.pending for a in of) and any(
        r.time > max(times) for a in of for r in a.reports)


def sendings(step: Send, state: State) -> list[float]:
    """The times of the calls that made `step`, as `repeated` counts them."""
    return [t for t in sent_at(state, step.to, step.message)
            if step.since is None or t > step.since]


def sent(state: State, to: str, message: str, mark: str | None = None) -> bool:
    """Whether an operator made the step that sends `to` the message
    `message`, with no error: a SendMessage call to `to` that holds
    `mark`, the part of the message that names what it gives, or where
    none is given the whole message, or the call `made` reads."""
    return bool(sent_at(state, to, message, mark))


def sends_to(state: State, to: str) -> list[Call]:
    """The operators' SendMessage calls to `to` that the harness gave no
    error, in the order they were made."""
    return sends_in(state.calls, to)


def sends_in(calls: Iterable[Call], to: str) -> list[Call]:
    """The SendMessage calls of `calls` to `to` that the harness gave no
    error, in the order they were made."""
    return sorted((c for c in calls if c.tool == Tool.SEND_MESSAGE
                   and c.input.get("to") == to and not c.error), key=lambda c: c.time)


def sent_with(state: State, to: str, text: str) -> list[float]:
    """The times of the calls of `sends_to` whose message holds `text`."""
    return [c.time for c in sends_to(state, to) if text in c.message]


def sent_at(state: State, to: str, message: str, mark: str | None = None) -> list[float]:
    """The times of the calls by which an operator made the step that sends
    `to` the message `message`, as `sent` reads them."""
    return sent_with(state, to, message if mark is None else mark) + [
        c.time for c in made_calls(state, Tool.SEND_MESSAGE, Send(to, message),
                                   lambda m: m.to == to and message.startswith(m.text))
        if not c.error and c.input.get("to") == to]


def made_calls(state: State, tool: Tool, step: Step, printed: Callable[[Made], bool]) -> list[Call]:
    """The calls of `tool` that `state.made` gives as made after the
    printing of `step`, a step of `tool`: by its key, or where the result
    cut the key, where `printed` holds of the printed step."""
    step_key = key(step)
    return [m.call for m in state.made if m.tool == tool and m.call.tool == tool.value
            and (m.key == step_key if m.key is not None else printed(m))]


def ask_again(state: State, to: str, replies: list[float], form: str) -> Send | bool:
    """`send_again` with the message that asks `to` to give its reply
    again in `form` (`messages.restate`)."""
    return send_again(state, to, replies, lambda t: messages.restate(t, form, messages.OPERATOR))


def send_again(state: State, to: str, replies: list[float],
               message: Callable[[float], str]) -> Send | bool:
    """`asked_again` for the operator, over the operators' SendMessage
    calls."""
    return asked_again(lambda who, text: sent_at(state, who, text), to, replies, message)


def asked_again(sent_times: Callable[[str, str], list[float]], to: str, replies: list[float],
                message: Callable[[float], str]) -> Send | bool:
    """The step on the latest of `replies`, the times of the replies of the
    agent `to`, in order, where that reply leaves the command a request to
    make of `to`: the request `message` gives for that reply's time,
    where `sent_times`, the times of the calls that sent a message to an
    agent, gives none. True where the reply before it
    had its request, sent before it: the reply that answers the request
    still leaves one, and the step is undecided. False where the
    request on it was sent and no reply of `to` followed it."""
    latest = replies[-1]
    before = [t for t in replies if t < latest]
    if before and any(at < latest for at in sent_times(to, message(before[-1]))):
        return True
    text = message(latest)
    return False if sent_times(to, text) else Send(to, text)


def bash_calls(state: State, command: str) -> list[Call]:
    """The operators' Bash calls that made the Bash step `command`, in the
    order they were made."""
    out = [c for c in state.calls
           if c.tool == Tool.BASH and command in str(c.input.get("command", ""))]
    out += made_calls(state, Tool.BASH, Bash(command), lambda m: m.text == command)
    return sorted({id(c): c for c in out}.values(), key=lambda c: c.time)


PRINTED_KEY = form(KEY_LINE, {"key": f"(?P<key>{STEP_KEY.pattern})", "command": "[^\n]*"}) + "\n"


@cache
def printed_opening() -> re.Pattern[str]:
    """The opening of the text `next` prints for a message or a Bash call
    in the foreground, from its key line, where the result holds it, up to
    the message or the command."""
    bash = opening(bash_text("{command}"), "command", {})
    return re.compile(f"^(?:{PRINTED_KEY})?(?:{send_opening()}|{bash})", re.MULTILINE)


def made(calls: Iterable[Call]) -> tuple[Made, ...]:
    """Each message and Bash call in the foreground that the result of an
    operator's call of `next` printed, with the call that operator made
    next, other than a call of `next` alone (`only_command`).
    The result may be cut, as by
    a pipe through `head` or `tail`: a step whose opening it cuts is not
    read, and one whose key it cuts is read with no key, and as far as the
    result gives it."""
    by: dict[str, list[Call]] = {}
    for c in sorted(calls, key=lambda c: c.time):
        by.setdefault(c.operator, []).append(c)
    out: list[Made] = []
    for operator, own in by.items():
        for c, after in zip(own, own[1:], strict=False):
            if (c.result is None or not next_call(c, operator)
                    or (after.tool == Tool.BASH
                        and only_command(str(after.input.get("command", "")), operator))):
                continue
            step = printed_step(c.result)
            if step is not None:
                out.append(Made(*step, after))
    return tuple(out)


def printed_step(result: str) -> tuple[str | None, Tool, str | None, str] | None:
    """The message or the Bash call in the foreground that `result`, the
    result of a call of `next`, prints, as `Made` gives it without the call,
    or None where it prints neither."""
    # The first opening: a message or a command may hold a line that
    # reads as one, and the key line comes before both.
    opening = printed_opening().search(result)
    if opening is None:
        return None
    tool = Tool.SEND_MESSAGE if opening["to"] is not None else Tool.BASH
    text = result[opening.end():].rstrip("\n")
    return (opening["key"], tool, opening["to"],
            unfenced(text) if tool is Tool.SEND_MESSAGE else text)
