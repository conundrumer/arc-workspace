"""The text the command prints for a step, with the key line before it
(`key_line`), and the lines of the operator's final reply.

Each printed prompt or message is fenced (`fenced`): the value to pass is
the text inside the fence, and its readers read a value given with or
without the fence lines (`unfenced`)."""

from pathlib import Path

from controlled_markdown import mctx
from operations.command_words import next_command
from operations.constants import COORDINATOR, FOREGROUND_MS
from operations.filing import filed_line, split_message
from operations.roles import description
from operations.steps import Bash, Launch, Poll, Reply, Send, Step, Undecided, key


FINAL_REPLY = "final reply"
"""The first line of the text `next` prints for the operator's final
reply, and of the message that sends the coordinator its text."""


SENT = mctx("My final reply went to {to} by SendMessage.")
"""The line an agent gives as its report after it sent its final reply by
SendMessage to the agent `to`."""


SENT_REPLY = SENT.format(to=COORDINATOR)


KEY_LINE = mctx("Step key: {key}. After the call below, run `{command}`.")


def key_line(step: Step, agent: str) -> str:
    """The line the command prints before a call it prints, which `handled.made`
    reads back. Nothing follows the call's last field, so an operator who
    copies that field copies no other line."""
    return KEY_LINE.format(key=key(step), command=next_command(agent))


FENCE = "```"


def fenced(value: str) -> str:
    return f"{FENCE}\n{value}\n{FENCE}"


def unfenced(value: str) -> str:
    """`value` without its opening fence line and its closing fence line,
    each where it has one: a printed value as far as a cut result gives
    it, or a value an operator passed with the fence lines."""
    head, sep, rest = value.partition("\n")
    if head == FENCE and sep:
        value = rest
    body, sep, tail = value.rpartition("\n")
    return body if sep and tail == FENCE else value


def send_text(to: str, message: str) -> str:
    return f"call SendMessage\nto: {to}\nmessage:\n{fenced(message)}"


def bash_text(command: str) -> str:
    return f"call Bash\ntimeout: {FOREGROUND_MS}\ncommand:\n{command}"


def printed(step: Step, agent: str, scratch: Path) -> str:
    """The text the command prints for `step`, for the operator whose agent
    id is `agent`, with the files `filing.filed` gives under `scratch`."""
    match step:
        case Launch(role, subject, _, model):
            extra = f"\nmodel: {model}" if model is not None else ""
            return (f"call Agent\ndescription: {description(role, subject)}\n"
                    f"subagent_type: {role.agent_type}\nrun_in_background: true{extra}\n"
                    f"prompt:\n{fenced(filed_line(step, scratch))}")
        case Send(to):
            head, rest = split_message(step)
            line = filed_line(step, scratch) if rest else ""
            return send_text(to, "\n".join(part for part in (head, line) if part))
        case Bash(command):
            return bash_text(command)
        case Poll():
            return mctx("Run the command again: nothing is ready.")
        case Reply():
            return f"{FINAL_REPLY}\n{SENT_REPLY}"
        case Undecided():
            raise ValueError(f"an undecided step is placed before it is printed: {step}")
