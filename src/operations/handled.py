"""Whether an operator already made or handled a step, read from the
operators' calls in the state.

Which call makes a step the command printed is as the HELP of `operate.py`
gives it, and `made` reads the call made right after `next`. A message
counts as made as well by each SendMessage call that holds the printed
message."""

import re
from collections.abc import Callable, Iterable
from functools import cache

from controlled_markdown import form
from operations import briefs
from operations.command_words import is_call, is_next, simple_commands
from operations.constants import COORDINATOR
from operations.printing import KEY_LINE, bash_text, opening, send_opening, unfenced
from operations.roles import Purpose
from operations.state import Agent, Call, Made, Printed, State
from operations.steps import STEP_KEY, UNDECIDED, Bash, Send, Step, Undecided, decision_key, key


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
                bool(given) and any(all(g in str(c.input.get("message", "")) for g in given)
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
    return sorted((c for c in state.calls if c.tool == "SendMessage"
                   and c.input.get("to") == to and not c.error), key=lambda c: c.time)


def sent_with(state: State, to: str, text: str) -> list[float]:
    """The times of the calls of `sends_to` whose message holds `text`."""
    return [c.time for c in sends_to(state, to) if text in str(c.input.get("message", ""))]


def sent_at(state: State, to: str, message: str, mark: str | None = None) -> list[float]:
    """The times of the calls by which an operator made the step that sends
    `to` the message `message`, as `sent` reads them."""
    return sent_with(state, to, message if mark is None else mark) + [
        c.time for c in made_calls(state, Printed.SEND_MESSAGE, Send(to, message),
                                   lambda m: m.to == to and message.startswith(m.text))
        if not c.error and c.input.get("to") == to]


def made_calls(state: State, tool: Printed, step: Step, printed: Callable[[Made], bool]) -> list[Call]:
    """The calls of `tool` that `state.made` gives as made after the
    printing of `step`, a step of `tool`: by its key, or where the result
    cut the key, where `printed` holds of the printed step."""
    step_key = key(step)
    return [m.call for m in state.made if m.tool == tool and m.call.tool == tool.value
            and (m.key == step_key if m.key is not None else printed(m))]


def ask_again(state: State, to: str, replies: list[float], form: str) -> Send | bool:
    """`asked_again` for the operator, over the operators' SendMessage
    calls."""
    return asked_again(lambda who, message: sent_at(state, who, message), to, replies, form,
                       briefs.OPERATOR)


def asked_again(sent_times: Callable[[str, str], list[float]], to: str, replies: list[float],
                form: str, reader: str) -> Send | bool:
    """The step on the latest of `replies`, the times of the replies of the
    agent `to` to `reader`, in order, where that reply is in no form the
    command reads: the message that asks `to` to give it again in `form`
    (`briefs.restate`), where `sent_times`, the times of the calls that
    sent a message to an agent, gives none. True where the reply before it
    had that request, sent before it: the reply that answers the request
    is still in no such form, and the step is undecided. False where the
    request on it was sent and no reply of `to` followed it."""
    latest = replies[-1]
    before = [t for t in replies if t < latest]
    if before and any(at < latest
                      for at in sent_times(to, briefs.restate(before[-1], form, reader))):
        return True
    message = briefs.restate(latest, form, reader)
    return False if sent_times(to, message) else Send(to, message)


def bash_calls(state: State, command: str) -> list[Call]:
    """The operators' Bash calls that made the Bash step `command`, in the
    order they were made."""
    out = [c for c in state.calls
           if c.tool == "Bash" and command in str(c.input.get("command", ""))]
    out += made_calls(state, Printed.BASH, Bash(command), lambda m: m.text == command)
    return sorted({id(c): c for c in out}.values(), key=lambda c: c.time)


def only_command(command: str, agent: str) -> bool:
    """Whether the Bash command `command` runs the command's `next` for the
    operator `agent` and nothing else but `cd` and `:`, which run no step
    the command prints."""
    return is_next(command, agent) and all(
        words[0] in ("cd", ":") or is_call(words, "next", agent)
        for words in simple_commands(command))


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
            command = str(c.input.get("command", ""))
            if (c.tool != "Bash" or c.result is None or not is_next(command, operator)
                    or (after.tool == "Bash"
                        and only_command(str(after.input.get("command", "")), operator))):
                continue
            # The first opening: a message or a command may hold a line
            # that reads as one, and the key line comes before both.
            opening = printed_opening().search(c.result)
            if opening is None:
                continue
            tool = Printed.SEND_MESSAGE if opening["to"] is not None else Printed.BASH
            text = c.result[opening.end():].rstrip("\n")
            out.append(Made(opening["key"], tool, opening["to"],
                            unfenced(text) if tool is Printed.SEND_MESSAGE else text, after))
    return tuple(out)
