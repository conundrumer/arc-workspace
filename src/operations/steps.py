"""The steps the command gives: each the one call the `operations` mod
makes next, with its parameters, and the fields that give it (`call`).

A brief, and a message to an agent other than the coordinator, goes to a
file the command writes before it gives the call (`filed`), and the
prompt or message given is the line `FILED` with that file's path. A
message to the coordinator that opens with `DECISION` keeps its first
line, which names what it gives, and files the rest. Each brief gives
the report file the agent writes its final reply to (`with_report`),
other than a solver pass's: the documents of a solver pass give its
report file. The readers of a launched agent's brief, of a message to it
and of its report read the file in place of the line, and read a message
an agent sent with or without fence lines (`unfenced`).

Which call makes a step is as the HELP of `operate.py` gives it. A
message counts as made as well by each SendMessage call that holds the
message given."""

import hashlib
import re
import shlex
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.constants import COORDINATOR, FOREGROUND_MS
from operations.roles import GENERAL_ROLES, PASSES, Model, Purpose, Role, description
from operations.state import Agent, Call, Made, Printed, State

BLOCK_SECONDS = (FOREGROUND_MS // 1000) - 30
"""The longest block of a command's `call`, under the timeout the mod
gives that call, `FOREGROUND_MS`, with room for the read of the state."""


@dataclass(frozen=True)
class Launch:
    """An Agent call, in the background, with no isolation. `model` gives
    the call's `model`. `items` is the
    number of items a brief that gives several items of the same work
    gives (`briefs.ITEM_LINES`), and None for any other brief; it stays
    out of the step's key, which its brief already fixes. `pipeline` is,
    for a solver pass, the time of the line that started its pipeline,
    and None for any other launch."""
    role: Role
    subject: str
    brief: str
    model: Model | None = None
    items: int | None = field(default=None, repr=False)
    pipeline: float | None = field(default=None, repr=False)


@dataclass(frozen=True)
class Send:
    """A SendMessage call."""
    to: str
    message: str


@dataclass(frozen=True)
class Bash:
    """A Bash call in the foreground, with the timeout `FOREGROUND_MS`."""
    command: str


@dataclass(frozen=True)
class Wait:
    """Nothing is ready, and an agent the loop launched runs or another
    holder holds a ticket of its scope: the loop waits, then reads the
    state again."""


@dataclass(frozen=True)
class Poll:
    """Nothing is ready yet: the loop reads the state again at once."""


@dataclass(frozen=True)
class Reply:
    """The loop's final reply, which ends it."""
    text: str


@dataclass(frozen=True)
class Undecided:
    """A step the command cannot place, which goes to a ticket analyst
    launched on it (`decisions`) and is never printed. The command reads back
    which analyst it went to by the decision key of `what`, so `what` is the
    same at each read of the same state. `given` holds the texts that a
    message by which the loop gave the coordinator this step holds each
    of, in a form other than `UNDECIDED` and `what`, where the step has
    such a form."""
    what: str
    given: tuple[str, ...] = field(default=(), repr=False)


UNDECIDED = "undecided:"
"""The first word of a message that gives the coordinator back a line of
its own in no form the command reads, and of a message by which the loop
gave the coordinator an undecided step
(`repeated`)."""

DECISION = "for the coordinator:"
"""The opening of a message that gives the coordinator labeled items to act
on: the `decision:` items of a ticket analyst's reply, or the note of a
blocked ticket as a `decision:` item."""


def unread_line(line: str) -> Send:
    """The message that gives the coordinator back its line `line`, in no
    form the command reads."""
    return Send(COORDINATOR, mctx("{opening} a line of the coordinator's in no form the "
                                  "command reads: {line}").format(opening=UNDECIDED, line=line))


def decided_by(state: State, step: Undecided) -> list[Agent]:
    """The ticket analysts the loop launched on
    `step`, in the order of their launch."""
    k = decision_key(step.what)
    return [a for a, purpose, keys in state.analysts() if purpose is Purpose.STEP and keys == [k]]


def agent_ids(agents: Iterable[Agent]) -> list[str] | Undecided:
    """The agent ids of `agents`, which a brief or a message gives, or the
    undecided step on the first of them whose id is unknown."""
    out: list[str] = []
    for a in agents:
        if a.agent_id is None:
            return Undecided(mctx("the {role} on {subject} has no known agent id, which a "
                                  "brief or a message names it by").format(
                role=a.role, subject=a.subject))
        out.append(a.agent_id)
    return out


def decision_key(what: str) -> str:
    """The key a `Decision:` line gives to rule the held step `what`."""
    return hashlib.sha1(what.encode()).hexdigest()[:KEY_LENGTH]


def held(what: str, choices: Mapping[str, str]) -> Undecided:
    """A step that holds its procedure until a `Decision:` line rules it,
    which gives its decision key and one of `choices`, each given with what
    it does."""
    given = "; ".join(f"`{c}`: {meaning}" for c, meaning in choices.items())
    return Undecided(what + mctx(". Rule it by the line `Decision: {key} <choice>`, with one "
                                 "of these choices: {given}.").format(key=decision_key(what),
                                                                      given=given))


type Step = Launch | Send | Undecided | Bash | Wait | Poll | Reply


def repeated(step: Step, state: State) -> bool:
    """Whether `step` is a message the loop already sent, or an
    undecided step that the loop already handled: a ticket analyst was
    launched on it, or the loop gave it to the coordinator, as
    `UNDECIDED` and its `what`, or in a message that holds each of its
    `given`. Its procedure then waits on the answer."""
    match step:
        case Undecided(what, given):
            return bool(decided_by(state, step)) or sent(state, COORDINATOR,
                                                       f"{UNDECIDED} {what}") or (
                bool(given) and any(all(g in str(c.input.get("message", "")) for g in given)
                                    for c in sends_to(state, COORDINATOR)))
        case Send(to, message):
            return sent(state, to, message)
        case _:
            return False


def sent(state: State, to: str, message: str, mark: str | None = None) -> bool:
    """Whether the loop made the step that sends `to` the message
    `message`, with no error: a SendMessage call to `to` that holds
    `mark`, the part of the message that names what it gives, or where
    none is given the whole message, or the call `made` reads."""
    return bool(sent_at(state, to, message, mark))


def sends_to(state: State, to: str) -> list[Call]:
    """The loop's SendMessage calls to `to` that the harness gave no
    error, in the order they were made."""
    return sorted((c for c in state.calls if c.tool == "SendMessage"
                   and c.input.get("to") == to and not c.error), key=lambda c: c.time)


def sent_at(state: State, to: str, message: str, mark: str | None = None) -> list[float]:
    """The times of the calls by which the loop made the step that sends
    `to` the message `message`, as `sent` reads them."""
    held = message if mark is None else mark
    return [c.time for c in sends_to(state, to) if held in str(c.input.get("message", ""))] + [
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
    """`asked_again` for the loop, over the loop's SendMessage
    calls."""
    return asked_again(lambda who, message: sent_at(state, who, message), to, replies, form,
                       briefs.LAUNCHER)


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
    """The loop's Bash calls that made the Bash step `command`, in the
    order they were made."""
    out = [c for c in state.calls
           if c.tool == "Bash" and command in str(c.input.get("command", ""))]
    out += made_calls(state, Printed.BASH, Bash(command), lambda m: m.text == command)
    return sorted({id(c): c for c in out}.values(), key=lambda c: c.time)


def key(step: Step) -> str:
    """The key of `step`, which is the same at each read of the state that
    gives the same step: the key an `Override: pass over` ruling gives
    (`directives.passed_over`). A solver pass's key is that of its task,
    its pass and its pipeline, so a ruling that passes it over holds
    whatever overrides its brief gains."""
    if isinstance(step, Launch) and step.role in PASSES:
        what = repr((step.role, step.subject, step.pipeline))
    else:
        what = repr(step)
    return hashlib.sha1(what.encode()).hexdigest()[:KEY_LENGTH]


COMMAND = "scripts/operate.py"
RUN_COMMAND = f"uv run python {COMMAND}"
"""How a step runs the command."""

KEY_LENGTH = 12

STEP_KEY = re.compile(rf"[0-9a-f]{{{KEY_LENGTH}}}")
OPERATORS = "();<>|&\n"
"""The characters of the shell's control and redirection operators."""


def simple_commands(command: str) -> list[list[str]]:
    """The words of each simple command of the Bash command `command`,
    without its redirections, or none where the shell's quoting in it is
    unbalanced. A redirection is an operator with `<` or `>`, the word
    after it, and a number before it."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=OPERATORS)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    out: list[list[str]] = [[]]
    redirect = False
    try:
        for word in lexer:
            if redirect:
                redirect = False
            elif set(word) <= set(OPERATORS) and set(word) & set("<>"):
                if out[-1] and out[-1][-1].isdigit():
                    out[-1].pop()
                redirect = True
            elif set(word) <= set(OPERATORS):
                out.append([])
            else:
                out[-1].append(word)
    except ValueError:
        return []
    return [words for words in out if words]


def passed(step: Step, state: State) -> str | None:
    """The line by which a ruling passed `step` over, or None."""
    return state.passed.get(key(step))




def nested(text: str) -> list[str]:
    """The lines of `text`, nested under an item of the final reply."""
    return [f"    {ln}".rstrip() for ln in text.strip().splitlines()]


def failure(c: Call) -> str:
    """The first line of the result of the failed call `c`."""
    reason = (c.result or "").strip().splitlines()
    return reason[0] if reason else mctx("no result text")


FILED = mctx("Read the file {path} first: it holds the text of this message.")
"""The line that gives the file a brief or a message is in."""

FILED_LINE = re.compile("^" + re.escape(FILED.format(path="\x00")).replace(
    "\x00", r"(?P<path>/[^\n]*?)") + "$", re.MULTILINE)

REPORT_NAME = re.compile(rf"{STEP_KEY.pattern}-report\.md")
"""The name of the report file a brief gives."""

FILES = "operations-files"
"""The directory under the session's scratchpad that holds the files the
command writes."""


def files_of(scratch: Path) -> Path:
    return scratch / FILES


def file_path(step: Step, scratch: Path) -> Path:
    """The file the brief of the launch `step`, or the filed part of the
    message `step`, is written to."""
    return files_of(scratch) / f"{key(step)}.md"


def report_path(step: Launch, scratch: Path) -> Path:
    return files_of(scratch) / f"{key(step)}-report.md"


def with_report(step: Launch, scratch: Path) -> Launch:
    """`step` with the line of its brief that gives its report file, other
    than a solver pass's."""
    if step.role in PASSES:
        return step
    form = briefs.REPORT_RULE if step.role in GENERAL_ROLES else briefs.REPORT_FILE
    line = form.format(path=report_path(step, scratch))
    return replace(step, brief=f"{step.brief}\n{line}")


def split_message(step: Send) -> tuple[str, str]:
    """The part of the message `step` printed in the call, and the part
    filed, as the module docstring gives them."""
    if step.to == COORDINATOR:
        if not step.message.startswith(DECISION):
            return step.message, ""
        head, _, rest = step.message.partition("\n")
        return head, rest
    return "", step.message


def filed(step: Step, scratch: Path) -> dict[Path, str]:
    """The files the command writes before it prints `step`, by path."""
    match step:
        case Launch(brief=brief):
            return {file_path(step, scratch): brief}
        case Send():
            rest = split_message(step)[1]
            return {file_path(step, scratch): rest} if rest else {}
        case _:
            return {}


def filed_line(step: Step, scratch: Path) -> str:
    return FILED.format(path=file_path(step, scratch))


FENCE = "```"


def unfenced(value: str) -> str:
    """`value` without its opening fence line and its closing fence line,
    each where it has one: a printed value as far as a cut result gives
    it, or a value an agent sent with the fence lines."""
    head, sep, rest = value.partition("\n")
    if head == FENCE and sep:
        value = rest
    body, sep, tail = value.rpartition("\n")
    return body if sep and tail == FENCE else value


def call(step: Step, scratch: Path, step_key: str) -> dict[str, object]:
    """The call `step` gives, as the fields the `operations` mod reads,
    with the files `filed` gives under `scratch`: `kind` names the call,
    and the other fields are its parameters. `step_key` is the key
    `key_line` gives the step, before `with_report` adds to its brief."""
    match step:
        case Launch(role, subject, _, model):
            return {"kind": "launch", "key": step_key, "description": description(role, subject),
                    "subagentType": role.agent_type,
                    "model": None if model is None else str(model),
                    "prompt": filed_line(step, scratch)}
        case Send(to):
            head, rest = split_message(step)
            line = filed_line(step, scratch) if rest else ""
            return {"kind": "send", "key": step_key, "to": to,
                    "message": "\n".join(part for part in (head, line) if part)}
        case Bash(command):
            return {"kind": "bash", "key": step_key, "command": command}
        case Wait() | Poll():
            return {"kind": "wait"}
        case Reply(text):
            return {"kind": "reply", "text": text}
        case Undecided():
            raise ValueError(f"an undecided step is placed before it is given: {step}")
