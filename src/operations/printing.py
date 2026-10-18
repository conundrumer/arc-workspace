"""The text the command prints for a step, with the key line before it
(`key_line`), or before the launches of one output (`batch_line`), the
SubagentHandback call that gives the agent's final reply (`REPLY_TEXT`), and the message that sends a final reply's text
(`final_message`).

Each printed prompt or message is fenced (`fenced`): the value to pass is
the text inside the fence, and its readers read a value given with or
without the fence lines (`unfenced`)."""

import re
from collections.abc import Sequence
from pathlib import Path

from controlled_markdown import form, mctx
from operations.command_words import Action, next_command
from operations.filing import filed_line, split_message
from operations.pacing import Capped, Pace, Scripted, Until
from operations.printed_forms import SENT
from operations.roles import launch_parameters, launched_type
from ticketing.times import utc_stamp
from operations.steps import Bash, EndTurn, Launch, Poll, Reply, Send, Step, Undecided, key


FINAL_REPLY = mctx("final reply")
"""The first line of the text `next` prints for the operator's final
reply, and of the message that sends the agent's parent its text."""


def final_message(text: str) -> str:
    """The message that sends the final reply whose text is `text`."""
    return f"{FINAL_REPLY}\n{text}"


def printed_line(pattern: str, text: str) -> bool:
    """Whether `text` holds a line that the regular expression `pattern`
    matches whole."""
    return re.search(f"^(?:{pattern})$", text, re.MULTILINE) is not None


def printed_reply(text: str) -> bool:
    """Whether `text`, a result of the command, prints a final reply
    (`REPLY_TEXT`)."""
    return printed_line(form(REPLY_TEXT, {"to": r"[^\n]+"}), text)


END_TURN = mctx("End your turn with no call: a message or your operator's end resumes you.")

END_TURN_LISTING = mctx("End your turn with no other call: the end of an agent you launched "
                        "resumes you, and can add the agent type {agent_type} to your agent "
                        "listing.")
"""The line of an end of turn held for the agent listing (`steps.ListingHold`)."""


def listing_line(held: Launch) -> str:
    return END_TURN_LISTING.format(agent_type=launched_type(held.role, held.subject))


def printed_end_turn(text: str) -> bool:
    """Whether `text`, a result of the command, prints the end of the
    agent's turn (`END_TURN`, `END_TURN_LISTING`)."""
    return printed_line(re.escape(END_TURN) + "|" + form(END_TURN_LISTING, {"agent_type": r"\S+"}),
                        text)


KEY_LINE = mctx("Step key {key}: after the call below, run `{command}`.")


def key_line(step: Step, agent: str, action: Action) -> str:
    """The line the command prints before a call it prints for the agent
    `agent` that runs `action`. Nothing follows the call's last field, so
    an operator who copies that field copies no other line."""
    return KEY_LINE.format(key=key(step), command=next_command(agent, action))


BATCH_LINE = mctx("Step keys {keys}: after the calls below, run `{command}`.")


def batch_line(steps: Sequence[Step], agent: str, action: Action) -> str:
    """The line the command prints before the launches `steps` of one
    output, in place of a key line for each (`key_line`)."""
    return BATCH_LINE.format(keys=", ".join(key(s) for s in steps),
                             command=next_command(agent, action))


FENCE = "```"


def fenced(value: str) -> str:
    return f"{FENCE}\n{value}\n{FENCE}"


def fence_split(value: str) -> tuple[bool, str, bool]:
    """`value` without its opening fence line and its closing fence line,
    each where it has one, between whether it has the opening one and
    whether it has the closing one."""
    head, sep, rest = value.partition("\n")
    opened = head == FENCE and bool(sep)
    if opened:
        value = rest
    body, sep, tail = value.rpartition("\n")
    closed = bool(sep) and tail == FENCE
    return opened, body if closed else value, closed


def unfenced(value: str) -> str:
    """`value` without its fence lines (`fence_split`): a printed value as
    far as a cut result gives it, or a value an operator passed with the
    fence lines."""
    return fence_split(value)[1]


SEND = "\n".join([mctx("call SendMessage"), mctx("to: {to}"), mctx("message:"), "{message}"])


REPLY_TEXT = "\n".join([
    FINAL_REPLY, mctx("call SubagentHandback"), mctx("message:"), fenced(SENT),
    mctx("Where the harness says SubagentHandback is not available, give the message as plain text.")])
"""The text the command prints for the final reply of an agent that sent
its text to the agent `to`: the SubagentHandback call whose message is the
line that says so."""


def send_text(to: str, message: str) -> str:
    return SEND.format(to=to, message=fenced(message))


def opening(text: str, last: str, holes: dict[str, str]) -> str:
    """The pattern of the printed `text` up to its hole `last`, with each
    hole of `holes` before it matched by its pattern."""
    return form(text[:text.index("{" + last + "}")], holes)


def send_opening() -> str:
    """The pattern of the printed message up to the message, its opening
    fence line included, with its recipient as the group `to`."""
    return opening(send_text("{to}", "{message}"), "message", {"to": r"(?P<to>[^\n]*)"})


def printed_send(text: str) -> tuple[str, str] | None:
    """The recipient and the unfenced message of the message that `text`, a
    result of `next`, prints, or None where it prints none, or one that the
    result cut before the closing fence of its message. The first opening
    is read: a message may hold a line that reads as one."""
    found = re.search(f"^{send_opening()}", text, re.MULTILINE)
    if found is None:
        return None
    message, sep, tail = text[found.end():].rstrip("\n").rpartition("\n")
    return (found["to"], message) if sep and tail == FENCE else None


LAUNCH = mctx("call Agent")
PROMPT = mctx("prompt")
FIELD = mctx("{name}: {value}")


def launch_text(fields: dict[str, str], prompt: str) -> str:
    """The text of a launch whose parameters other than its prompt are
    `fields`, in their order, which `printed_launch` reads back."""
    return "\n".join([LAUNCH, *(FIELD.format(name=k, value=v) for k, v in fields.items()),
                      f"{PROMPT}:", fenced(prompt)])


def printed_launches(text: str) -> list[dict[str, str] | None]:
    """The parameters of each launch that `text`, a result of `next`,
    prints, in its order, None for one that the result cut before the
    closing fence of its prompt."""
    lines = text.rstrip("\n").split("\n")
    starts = [i for i, line in enumerate(lines) if line == LAUNCH]
    return [launch_fields(lines[a + 1:b]) for a, b in zip(starts, [*starts[1:], len(lines)])]


def printed_launch(text: str) -> dict[str, str] | None:
    """The parameters of the last launch that `text`, a result of `next`,
    prints, or None where it prints no launch, or one that the result cut
    before the closing fence of its prompt."""
    found = printed_launches(text)
    return found[-1] if found else None


def launch_fields(lines: list[str]) -> dict[str, str] | None:
    """The parameters of the launch whose lines after its first are
    `lines`, or None where they end before the closing fence of its
    prompt."""
    fields: dict[str, str] = {}
    for i, line in enumerate(lines):
        if line == f"{PROMPT}:":
            opened, prompt, closed = fence_split("\n".join(lines[i + 1:]))
            if not (opened and closed):
                return None
            return fields | {PROMPT: prompt}
        name, sep, value = line.partition(": ")
        if not sep:
            return None
        fields[name] = value
    return None


def pace_line(pace: Pace | Capped | None) -> str | None:
    """The line that gives how the usage pace holds back agent starts."""
    match pace:
        case Capped(cap):
            return mctx("The usage pace's cap of {cap} running agents holds back agent starts.").format(
                cap=cap)
        case Until(time):
            return mctx("No agent starts past the usage pace until {time}.").format(
                time=utc_stamp(time))
        case Scripted(path):
            return mctx("The pace of the script {path} holds back agent starts.").format(path=path)
        case _:
            return None


def printed(step: Step, agent: str, scratch: Path) -> str:
    """The text the command prints for `step`, for the operator whose agent
    id is `agent`, with the files `filing.filed` gives under `scratch`."""
    match step:
        case Launch(role, subject, _, model):
            return launch_text(launch_parameters(role, subject, model), filed_line(step, scratch))
        case Send(to):
            head, rest = split_message(step)
            line = filed_line(step, scratch) if rest else ""
            return send_text(to, "\n".join(part for part in (head, line) if part))
        case Poll(pace):
            again = mctx("Run the command again: nothing is ready.")
            return "\n".join([*([held] if (held := pace_line(pace)) else []), again])
        case EndTurn(hold):
            if hold is None:
                return END_TURN
            line = listing_line(hold.launch)
            wait = step.wait
            return line if wait is None else printed(wait, agent, scratch) + "\n" + line
        case Reply(to):
            return REPLY_TEXT.format(to=to)
        case Undecided():
            raise ValueError(f"an undecided step is placed before it is printed: {step}")
        case Bash():
            raise ValueError(f"a Bash step is run by the command, not printed: {step}")
