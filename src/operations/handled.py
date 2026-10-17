"""Whether an operator already made or handled a step: a message, read
from the step journal (`journal`), and an undecided step, read from the
ticket analysts launched on it."""

from collections.abc import Callable, Iterable

from controlled_markdown import mctx
from operations import messages
from operations.constants import COORDINATOR
from operations.journal import Due, Entry, due
from operations.roles import Purpose
from operations.state import Agent, Call, State, Ticket, Tool
from operations.steps import (UNDECIDED, Bash, Journaled, Launch, Send, Step, Undecided,
                              analyst_key, key)


def decided_by(state: State, step: Undecided) -> list[Agent]:
    """The ticket analysts of any operator of the session launched on
    `step`, in the order of their launch."""
    k = analyst_key(step)
    return [a for a, purpose, keys in state.analysts() if purpose is Purpose.STEP and keys == [k]]


def held_aside(state: State, step: Step) -> bool:
    """Whether `State.aside`, the set of the keys of the steps `order.batch`
    set aside, holds `step`."""
    return bool(state.aside) and key(step) in state.aside


def repeated(step: Step, state: State) -> bool:
    """Whether `step` is a step `state.aside` holds, a message the journal
    gives as done (`done`), a launch or a Bash step the journal holds back
    (`journal.due`), a message an operator already sent, or an
    undecided step that an operator already handled: a ticket analyst was
    launched on it, or an operator gave it to the coordinator, as
    `steps.UNDECIDED` and its `what`, or in a message that holds each of its
    `given`. Its procedure then waits on the answer."""
    if held_aside(state, step):
        return True
    match step:
        case Undecided(what, given):
            return bool(decided_by(state, step)) or sent(state, COORDINATOR,
                                                       f"{UNDECIDED} {what}") or (
                bool(given) and any(all(g in e.text for g in given)
                                    for e in sends_to(state, COORDINATOR)))
        case Send():
            return done(state, step) or bool(sendings(step, state))
        case Launch() | Bash():
            return due(state.journal, step, state.now) is Due.WAIT
        case _:
            return False


def answered(step: Send, state: State) -> bool:
    """Whether an operator already sent `step`, as `repeated` reads it,
    and its recipient does not run and reported after its latest
    sending."""
    times = sendings(step, state)
    if not times:
        return False
    of = [a for a in state.transcripts.agents if a.agent_id == step.to]
    return not any(a.pending for a in of) and any(
        r.time > max(times) for a in of for r in a.reports)


def sendings(step: Send, state: State) -> list[float]:
    """The times of the messages that made `step`, as `repeated` counts
    them."""
    return [t for t in sent_at(state, step.to, step.message)
            if step.since is None or t > step.since]


def done(state: State, step: Journaled) -> bool:
    """Whether the journal gives `step` as done: a procedure whose step is
    done goes on past it."""
    return any(e.done for e in state.journal.of(key(step)))


def sent(state: State, to: str, message: str, mark: str | None = None) -> bool:
    """Whether an operator made the step that sends `to` the message
    `message`, as the journal gives it (`sent_at`): a message to `to` done
    that holds `mark`, the part of the message that names what it gives,
    or where none is given the whole message."""
    return bool(sent_at(state, to, message, mark))


def sends_to(state: State, to: str) -> list[Entry]:
    """The messages to `to` that the journal gives as done, in the order
    they were given."""
    return state.journal.sent(to)


def sends_in(calls: Iterable[Call], to: str) -> list[Call]:
    """The SendMessage calls of `calls` to `to` that the harness gave no
    error, in the order they were made."""
    return sorted((c for c in calls if c.tool == Tool.SEND_MESSAGE
                   and c.input.get("to") == to and not c.error), key=lambda c: c.time)


def sent_with(state: State, to: str, text: str) -> list[float]:
    """The times of the messages of `sends_to` that hold `text`."""
    return [e.close.time for e in sends_to(state, to) if e.close is not None and text in e.text]


def sent_at(state: State, to: str, message: str, mark: str | None = None) -> list[float]:
    """The times of the messages by which an operator made the step that
    sends `to` the message `message`, as `sent` reads them."""
    return sent_with(state, to, message if mark is None else mark)


def ask_again(state: State, to: str, replies: list[float], form: str) -> Send | bool:
    """`send_again` with the message that asks `to` to give its reply
    again in `form` (`messages.restate`)."""
    return send_again(state, to, replies, lambda t: messages.restate(t, form, messages.OPERATOR),
                      form)


def send_again(state: State, to: str, replies: list[float],
               message: Callable[[float], str], about: str) -> Send | bool:
    """The step on the latest of `replies`, the times of the replies of the
    agent `to`, in order, where that reply leaves the command a request to
    make of `to`: the request `message` gives for that reply's time, named
    by `about` and that time, where no message of it was sent (`sent_at`).
    True where the reply before it had its request, sent before it: the
    reply that answers the request still leaves one, and the step is
    undecided. False where the request on it was sent and no reply of `to`
    followed it."""
    latest = replies[-1]
    before = [t for t in replies if t < latest]
    if before and any(at < latest for at in sent_at(state, to, message(before[-1]))):
        return True
    text = message(latest)
    return False if sent_at(state, to, text) else Send(to, text, f"{about} {latest}")


def bash_calls(state: State, command: str) -> tuple[Call, ...]:
    """The operators' Bash calls and the Bash steps of the journal
    (`TranscriptsRead.calls`) that ran the command `command`, among others,
    in the order they were made."""
    found = state.transcripts.bash_found
    if command not in found:
        found[command] = tuple(c for c in state.transcripts.calls
                               if c.tool == Tool.BASH and command in str(c.input.get("command", "")))
    return found[command]


def unmoved(t: Ticket, s: Send) -> Undecided:
    """The step of the change `t` whose next step `s` is a message its
    recipient already answered, with the change where it was."""
    return Undecided(mctx("the next step of change {number} is the message {key} to {agent}, "
                          "which an operator already sent and {agent} answered, and the "
                          "change has not moved since").format(
        number=t.number, key=key(s), agent=s.to))
