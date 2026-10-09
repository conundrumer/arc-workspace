"""The steps the command prints: each the one call the operator agent makes
next, with its parameters, and the text that prints it.

A brief, and a message to an agent other than the coordinator, goes to a
file the command writes before it prints the call (`filed`), and the
printed prompt or message is the line `FILED` with that file's path. Each
printed prompt or message is fenced (`fenced`): the value to pass is the
text inside the fence, and its readers read a value given with or without
the fence lines (`unfenced`). A
message to the coordinator that opens with `DECISION` keeps its first
line, which names what it gives, and files the rest. Each brief gives
the report file the agent writes its final reply to (`with_report`),
other than a solver pass's: the documents of a solver pass give its
report file. The readers of a launched agent's brief, of a message to it
and of its report read the file in place of the line.

Which call makes a step the command printed is as the HELP of `operate.py`
gives it, and `made` reads the call made right after `next`. A message
counts as made as well by each SendMessage call that holds the printed
message."""

import hashlib
import re
import shlex
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.constants import COORDINATOR, FOREGROUND_MS, WAIT_SECONDS
from operations.roles import GENERAL_ROLES, PASSES, Model, Purpose, Role, description
from operations.state import Agent, Call, Made, Printed, State

BLOCK_SECONDS = (FOREGROUND_MS // 1000) - 30
"""The longest foreground block of a command's `next`, under the bound on
a foreground call, with room for the read of the state."""

WAIT_CAP = 11
"""How many waits in a row may end on `WAIT_SECONDS` with no message, no
report and no step between them, as the section `keep-alive-timer` of
`prompts/agents/notes/commands.md` caps the keep-alive timer."""


@dataclass(frozen=True)
class Launch:
    """An Agent call, in the background, with no isolation. `model` gives
    the call's `model`. `items` is the
    number of items a brief that gives several items of the same work
    gives (`briefs.ITEM_LINES`), and None for any other brief; it stays
    out of the step's key, which its brief already fixes."""
    role: Role
    subject: str
    brief: str
    model: Model | None = None
    items: int | None = field(default=None, repr=False)


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
class StopWait:
    """A TaskStop call on a command of the operator's, by the ID the
    harness gave it."""
    task_id: str


@dataclass(frozen=True)
class Wait:
    """The command's wait, in the background, after which the agent ends
    its turn: `operate.py wait` with the agent's id."""


@dataclass(frozen=True)
class EndTurn:
    """The agent ends its turn with no call: the command's wait already
    runs in the background, or, where `capped`, the waits reached
    `WAIT_CAP`, and a message or a report wakes the agent."""
    capped: bool = False


@dataclass(frozen=True)
class Poll:
    """Nothing is ready yet, and nothing an agent of the operator's runs is
    waited on: the agent runs the command again at once."""


@dataclass(frozen=True)
class Reply:
    """The operator's final reply."""
    text: str


@dataclass(frozen=True)
class Relay:
    """The decision lines `lines` of the ticket analyst `agent` on the held
    step `what`, whose launcher printed its final reply after the analyst's
    launch, printed to the operator whose procedure meets that step, which
    applies them as the lines of an analyst it launched."""
    agent: str
    what: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class Undecided:
    """A step the command cannot place, which goes to a ticket analyst
    launched on it (`decisions`) and is never printed. The command reads back
    which analyst it went to by the decision key of `what`, so `what` is the
    same at each read of the same state. `given` holds the texts that a
    message by which an operator gave the coordinator this step holds each
    of, in a form other than `UNDECIDED` and `what`, where the step has
    such a form."""
    what: str
    given: tuple[str, ...] = field(default=(), repr=False)


UNDECIDED = "undecided:"
"""The first word of a message that gives the coordinator back a line of
its own in no form the command reads, and of a message by which an
operator in an earlier transcript gave the coordinator an undecided step
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
    """The ticket analysts of any operator of the session launched on
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


type Step = Launch | Send | Undecided | Relay | Bash | StopWait | Wait | EndTurn | Poll | Reply


def repeated(step: Step, state: State) -> bool:
    """Whether `step` is a message an operator already sent, or an
    undecided step that an operator already handled: a ticket analyst was
    launched on it, or an operator gave it to the coordinator, as
    `UNDECIDED` and its `what`, or in a message that holds each of its
    `given`. Its procedure then waits on the answer."""
    match step:
        case Undecided(what, given):
            return bool(decided_by(state, step)) or sent(state, COORDINATOR,
                                                       f"{UNDECIDED} {what}") or (
                bool(given) and any(all(g in str(c.input.get("message", "")) for g in given)
                                    for c in sends_to(state, COORDINATOR)))
        case Relay(agent, what):
            head = RELAY_HEAD.format(agent=agent, key=decision_key(what))
            return any(c.tool == "Bash" and head in (c.result or "") for c in state.calls)
        case Send(to, message):
            return sent(state, to, message)
        case _:
            return False


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


def sent_at(state: State, to: str, message: str, mark: str | None = None) -> list[float]:
    """The times of the calls by which an operator made the step that sends
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


def key(step: Step) -> str:
    """The key of `step`, which is the same at each read of the state that
    gives the same step: the key the operator gives `operate.py pass-over`
    for a step that an `Override:` or `Decision:` line rules out."""
    return hashlib.sha1(repr(step).encode()).hexdigest()[:KEY_LENGTH]


COMMAND = "scripts/operate.py"
RUN_COMMAND = f"uv run python {COMMAND}"
"""How a printed step runs the command."""

KEY_LENGTH = 12
PASS_OVER = "pass-over"


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


def pass_overs(command: str) -> list[tuple[str, str]]:
    """The key and the line of each call of `operate.py pass-over` that the
    Bash command `command` runs, with a key in the form `key` gives and
    one line."""
    head = [*RUN_COMMAND.split(), PASS_OVER]
    return [(words[-2], words[-1]) for words in simple_commands(command)
            if words[:len(head)] == head and len(words) == len(head) + 3
            and STEP_KEY.fullmatch(words[-2])]


def passed_over_line(step_key: str) -> str:
    """The line `operate.py pass-over` prints for the step `step_key`."""
    return mctx("Step {key} is passed over.").format(key=step_key)


def passed(step: Step, state: State) -> str | None:
    """The line by which an operator passed `step` over, or None."""
    return state.passed.get(key(step))


def wait_command(agent: str) -> str:
    return f": 'unattended-wait: operate.py wait'; {' '.join(run_words('wait', agent))}"


def next_command(agent: str) -> str:
    return " ".join(run_words("next", agent))


def run_words(action: str, agent: str) -> list[str]:
    """The words of the call of `operate.py` with `action` for the operator
    `agent`."""
    return [*RUN_COMMAND.split(), action, agent]


def runs(command: str, action: str, agent: str) -> bool:
    """Whether the Bash command `command` runs `operate.py` with `action`
    for the operator `agent`, whatever else it runs."""
    return any(words == run_words(action, agent) for words in simple_commands(command))


def is_wait(command: str, agent: str) -> bool:
    return runs(command, "wait", agent)


def is_next(command: str, agent: str) -> bool:
    return runs(command, "next", agent)


FINAL_REPLY = "final reply"
"""The first line of the text `next` prints for the operator's final
reply."""


def final_replies(state: State, operator: str) -> list[float]:
    """The times of the calls of `next` that printed `operator` its final
    reply."""
    return [c.time for c in state.calls if c.operator == operator and c.tool == "Bash"
            and is_next(str(c.input.get("command", "")), operator)
            and (c.result or "").startswith(FINAL_REPLY + "\n")]


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


RELAY_HEAD = mctx("Ticket analyst {agent} decided the held step {key} below, and the operator "
                  "that launched it has printed its final reply since.")
RELAY_APPLY = mctx("Apply the lines below as lines of a ticket analyst you launched to rule a "
                   "step, then run `{command}`.")


def only_command(command: str, agent: str) -> bool:
    """Whether the Bash command `command` runs the command's `wait` or
    `next` for the operator `agent` and nothing else but `cd` and `:`."""
    want = [run_words(action, agent) for action in ("wait", "next")]
    found = simple_commands(command)
    return any(words in want for words in found) and all(
        words[0] in ("cd", ":") or words in want for words in found)


KEY_LINE = mctx("Step key: {key}. After the call below, run `{command}`.")


def key_line(step: Step, agent: str) -> str:
    """The line the command prints before a call it prints, which `made`
    reads back. Nothing follows the call's last field, so an operator who
    copies that field copies no other line."""
    return KEY_LINE.format(key=key(step), command=next_command(agent))


PRINTED_KEY = (re.escape(KEY_LINE.format(key="\x00", command="\x01"))
               .replace("\x00", f"(?P<key>{STEP_KEY.pattern})")
               .replace("\x01", "[^\n]*") + "\n")


def opening(text: str, *fields: tuple[str, str]) -> str:
    """The pattern of the printed `text` up to its last field, where `text`
    holds a stand-in for each field of `fields`, given with the pattern of
    its value; the last stand-in ends the opening."""
    out = re.escape(text[:text.index(fields[-1][0])])
    for stand_in, pattern in fields[:-1]:
        out = out.replace(re.escape(stand_in), pattern)
    return out


@cache
def printed_opening() -> re.Pattern[str]:
    """The opening of the text `next` prints for a message or a Bash call
    in the foreground, from its key line, where the result holds it, up to
    the message or the command."""
    send = opening(send_text("\x00", "\x01"), ("\x00", r"(?P<to>[^\n]*)"), ("\x01", ""))
    bash = opening(bash_text("\x01"), ("\x01", ""))
    return re.compile(f"^(?:{PRINTED_KEY})?(?:{send}|{bash})", re.MULTILINE)


def made(calls: Iterable[Call]) -> tuple[Made, ...]:
    """Each message and Bash call in the foreground that the result of an
    operator's call of `next` printed, with the call that operator made
    next, other than a call of `wait` or `next` alone (`only_command`).
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


FILED = mctx("Read the file {path} first: it holds the text of this message.")
"""The line that gives the file a brief or a message is in."""

FILED_LINE = re.compile("^" + re.escape(FILED.format(path="\x00")).replace(
    "\x00", r"(?P<path>/[^\n]*?)") + "$", re.MULTILINE)

REPORT_NAME = re.compile(rf"{STEP_KEY.pattern}-report\.md")
"""The name of the report file a brief gives."""

FILES = "operator-files"
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
    id is `agent`, with the files `filed` gives under `scratch`."""
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
        case StopWait(task_id):
            return f"call TaskStop\ntask_id: {task_id}"
        case Wait():
            return (f"call Bash\nrun_in_background: true\ntimeout: 7200000\ncommand:\n"
                    f"{wait_command(agent)}\n" + mctx("Then end your turn."))
        case EndTurn(capped=False):
            return mctx("End your turn with no call: the command's wait runs.")
        case EndTurn():
            return mctx("End your turn with no call: no wait is started, and a message or "
                        "a report wakes you.")
        case Poll():
            return mctx("Run the command again: nothing is ready.")
        case Reply(text):
            return f"{FINAL_REPLY}\n{text}"
        case Relay(analyst, what, lines):
            return "\n".join([RELAY_HEAD.format(agent=analyst, key=decision_key(what)),
                              RELAY_APPLY.format(command=next_command(agent)),
                              "", *lines, "", what])
        case Undecided():
            raise ValueError(f"an undecided step is placed before it is printed: {step}")
