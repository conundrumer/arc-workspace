"""The text the command prints for a step, with the key line before it
(`key_line`), and the lines of the operator's final reply.

Each printed prompt or message is fenced (`fenced`): the value to pass is
the text inside the fence, and its readers read a value given with or
without the fence lines (`unfenced`)."""

import re
from pathlib import Path

from controlled_markdown import form, mctx
from operations.command_words import next_command
from operations.constants import FOREGROUND_MS
from operations.filing import filed_line, split_message
from operations.roles import description
from operations.steps import Bash, EndTurn, Launch, Poll, Reply, Send, Step, Undecided, key


FINAL_REPLY = mctx("final reply")
"""The first line of the text `next` prints for the operator's final
reply, and of the message that sends the agent's parent its text."""


SENT = mctx("My final reply went to {to} by SendMessage.")
"""The line an agent gives as its report after it sent its final reply by
SendMessage to the agent `to`."""


REPLY_TEXT = f"{FINAL_REPLY}\n{SENT}"
"""The text the command prints for the final reply of an agent that sent
its text to the agent `to`."""


def printed_reply(text: str) -> bool:
    """Whether `text`, a result of the command, prints a final reply
    (`REPLY_TEXT`)."""
    return re.search("^" + form(REPLY_TEXT, {"to": r"[^\n]+"}) + "$", text,
                     re.MULTILINE) is not None


END_TURN = mctx("End your turn with no call: a message or your operator's end resumes you.")


def printed_end_turn(text: str) -> bool:
    """Whether `text`, a result of the command, prints the end of the
    agent's turn (`END_TURN`)."""
    return re.search("^" + re.escape(END_TURN) + "$", text, re.MULTILINE) is not None


KEY_LINE = mctx("Step key: {key}. After the call below, run `{command}`.")


def key_line(step: Step, agent: str, action: str) -> str:
    """The line the command prints before a call it prints for the agent
    `agent` that runs `action`, which `handled.made` reads back. Nothing
    follows the call's last field, so an operator who copies that field
    copies no other line."""
    return KEY_LINE.format(key=key(step), command=next_command(agent, action))


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
BASH = "\n".join([mctx("call Bash"), mctx("timeout: {timeout}"), mctx("command:"), "{command}"])


def send_text(to: str, message: str) -> str:
    return SEND.format(to=to, message=fenced(message))


def bash_text(command: str) -> str:
    return BASH.format(timeout=FOREGROUND_MS, command=command)


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


def parameter(value: object) -> str:
    """A parameter of a call as the command prints it."""
    return str(value).lower() if isinstance(value, bool) else str(value)


def launch_text(fields: dict[str, str], prompt: str) -> str:
    """The text of a launch whose parameters other than its prompt are
    `fields`, in their order, which `printed_launch` reads back."""
    return "\n".join([LAUNCH, *(FIELD.format(name=k, value=v) for k, v in fields.items()),
                      f"{PROMPT}:", fenced(prompt)])


def printed_launch(text: str) -> dict[str, str] | None:
    """The parameters of the last launch that `text`, a result of `next`,
    prints, or None where it prints no launch, or one that the result cut
    before the closing fence of its prompt."""
    lines = text.rstrip("\n").split("\n")
    if LAUNCH not in lines:
        return None
    at = len(lines) - 1 - lines[::-1].index(LAUNCH)
    fields: dict[str, str] = {}
    for i in range(at + 1, len(lines)):
        if lines[i] == f"{PROMPT}:":
            opened, prompt, closed = fence_split("\n".join(lines[i + 1:]))
            if not (opened and closed):
                return None
            return fields | {PROMPT: prompt}
        name, sep, value = lines[i].partition(": ")
        if not sep:
            return None
        fields[name] = value
    return None


def printed(step: Step, agent: str, scratch: Path) -> str:
    """The text the command prints for `step`, for the operator whose agent
    id is `agent`, with the files `filing.filed` gives under `scratch`."""
    match step:
        case Launch(role, subject, _, model):
            fields = {"description": description(role, subject),
                      "subagent_type": role.agent_type, "run_in_background": parameter(True)}
            return launch_text(fields | ({"model": model} if model is not None else {}),
                               filed_line(step, scratch))
        case Send(to):
            head, rest = split_message(step)
            line = filed_line(step, scratch) if rest else ""
            return send_text(to, "\n".join(part for part in (head, line) if part))
        case Bash(command):
            return bash_text(command)
        case Poll():
            return mctx("Run the command again: nothing is ready.")
        case EndTurn():
            return END_TURN
        case Reply(to):
            return REPLY_TEXT.format(to=to)
        case Undecided():
            raise ValueError(f"an undecided step is placed before it is printed: {step}")
