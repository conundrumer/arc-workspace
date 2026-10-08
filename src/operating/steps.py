"""The steps the command prints: each the one call the operator agent makes
next, with its parameters in full, and the text that prints it.

Which call makes a step the command printed is as the HELP of `operate.py`
gives it, and `made` reads the call made right after `next`. A message
counts as made as well by each SendMessage call that holds the printed
message."""

import hashlib
import re
import shlex
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cache

from controlled_markdown import mctx
from operating import briefs
from operating.bounds import COORDINATOR, FOREGROUND_MS, WAIT_SECONDS
from operating.roles import Model, Role, description
from operating.state import Agent, Call, Made, State

WAIT_CAP = 11
"""How many waits in a row may end on `WAIT_SECONDS` with no message, no
report and no step between them, as the section `keep-alive-timer` of
`prompts/agents/notes/commands.md` caps the keep-alive timer."""


@dataclass(frozen=True)
class Launch:
    """An Agent call, in the background. `worktree` gives the Agent tool's
    `isolation: "worktree"`, and `model` the call's `model`."""
    role: Role
    subject: str
    brief: str
    worktree: bool = False
    model: Model | None = None


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
class Stop:
    """A TaskStop call on a command of the operator's, by the ID the
    harness gave it."""
    task_id: str


@dataclass(frozen=True)
class Wait:
    """The command's wait, in the background, after which the agent ends
    its turn: `operate.py wait` with the agent's id. `on` names what the
    wait is for."""
    on: str


@dataclass(frozen=True)
class EndTurn:
    """The agent ends its turn with no call: the command's wait already
    runs in the background, or, where `capped`, the waits reached
    `WAIT_CAP`, and a message or a report wakes the agent."""
    on: str
    capped: bool = False


@dataclass(frozen=True)
class Again:
    """Nothing is ready yet, and nothing an agent of the operator's runs is
    waited on: the agent runs the command again at once."""
    on: str


@dataclass(frozen=True)
class Reply:
    """The operator's final reply."""
    text: str


UNDECIDED = "undecided:"
"""The first word of a message that gives the coordinator a step the
command cannot place."""

DECISION = "for the coordinator:"
"""The opening of a message that gives the coordinator labeled items to act
on: the part of a ticket analyst's reply for the coordinator, or the note of
a blocked ticket as a `decision:` item."""


def undecided(what: str) -> Send:
    """A step the command cannot place, given to the coordinator. The
    command reads back that it was sent by its text, so `what` is the same
    at each read of the same state."""
    return Send(COORDINATOR, f"{UNDECIDED} {what}")


def agent_ids(agents: Iterable[Agent]) -> list[str] | Send:
    """The agent ids of `agents`, which a brief or a message gives, or the
    undecided step on the first of them whose id is unknown."""
    out: list[str] = []
    for a in agents:
        if a.agent_id is None:
            return undecided(mctx("the {role} on {subject} has no known agent id, which a "
                                  "brief or a message names it by").format(
                role=a.role, subject=a.subject))
        out.append(a.agent_id)
    return out


def ruling_key(what: str) -> str:
    """The key a `Decision:` line gives to rule the held step `what`."""
    return hashlib.sha1(what.encode()).hexdigest()[:KEY_LENGTH]


def held(what: str, choices: Mapping[str, str]) -> Send:
    """A step that holds its procedure until the coordinator rules it, by
    a `Decision:` line that gives its ruling key and one of `choices`, each
    given with what it does."""
    given = "; ".join(f"`{c}`: {meaning}" for c, meaning in choices.items())
    return undecided(what + mctx(". Rule it by the line `Decision: {key} <choice>`, with one "
                                 "of these choices: {given}.").format(key=ruling_key(what),
                                                                      given=given))


type Step = Launch | Send | Bash | Stop | Wait | EndTurn | Again | Reply


def repeated(step: Step, state: State) -> bool:
    """Whether `step` is a message an operator already sent: a step whose
    procedure then waits on its answer."""
    return isinstance(step, Send) and sent(state, step.to, step.message)


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
        c.time for c in made_calls(state, "SendMessage", Send(to, message),
                                   lambda m: m.to == to and message.startswith(m.text))
        if not c.error and c.input.get("to") == to]


def made_calls(state: State, tool: str, step: Step, printed: Callable[[Made], bool]) -> list[Call]:
    """The calls of `tool` that `state.made` gives as made after the
    printing of `step`, a step of `tool`: by its key, or where the result
    cut the key, where `printed` holds of the printed step."""
    step_key = key(step)
    return [m.call for m in state.made if m.tool == tool and m.call.tool == tool
            and (m.key == step_key if m.key is not None else printed(m))]


def ask_again(state: State, to: str, replies: list[float], form: str) -> Send | bool:
    """The step on the latest of `replies`, the times of the replies of the
    agent `to`, in order, where that reply is in no form the command reads:
    the message that asks `to` to give it again in `form`
    (`briefs.restate`), where no operator sent it. True where the reply
    before it had that request, sent before it: the reply that answers the
    request is still in no such form, and the step goes to the coordinator.
    False where the request on it was sent and no reply of `to` followed
    it."""
    latest = replies[-1]
    before = [t for t in replies if t < latest]
    if before and any(at < latest
                      for at in sent_at(state, to, briefs.restate(before[-1], form))):
        return True
    message = briefs.restate(latest, form)
    return False if sent(state, to, message) else Send(to, message)


def bash_calls(state: State, command: str) -> list[Call]:
    """The operators' Bash calls that made the Bash step `command`, in the
    order they were made."""
    out = [c for c in state.calls
           if c.tool == "Bash" and command in str(c.input.get("command", ""))]
    out += made_calls(state, "Bash", Bash(command), lambda m: m.text == command)
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


def opening(step: Step, *fields: tuple[str, str]) -> str:
    """The pattern of the text `printed` gives `step` up to its last
    field, where `step` holds a stand-in for each field of `fields`, given
    with the pattern of its value; the last stand-in ends the opening."""
    text = printed(step, "")
    out = re.escape(text[:text.index(fields[-1][0])])
    for stand_in, pattern in fields[:-1]:
        out = out.replace(re.escape(stand_in), pattern)
    return out


@cache
def printed_opening() -> re.Pattern[str]:
    """The opening of the text `next` prints for a message or a Bash call
    in the foreground, from its key line, where the result holds it, up to
    the message or the command."""
    send = opening(Send("\x00", "\x01"), ("\x00", r"(?P<to>[^\n]*)"), ("\x01", ""))
    bash = opening(Bash("\x01"), ("\x01", ""))
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
            tool = "SendMessage" if opening["to"] is not None else "Bash"
            out.append(Made(opening["key"], tool, opening["to"],
                            c.result[opening.end():].rstrip("\n"), after))
    return tuple(out)


def printed(step: Step, agent: str) -> str:
    """The text the command prints for `step`, for the operator whose agent
    id is `agent`."""
    match step:
        case Launch(role, subject, brief, worktree, model):
            iso = '\nisolation: "worktree"' if worktree else ""
            iso += f"\nmodel: {model}" if model is not None else ""
            return (f"call Agent\ndescription: {description(role, subject)}\n"
                    f"subagent_type: {role.agent_type}\nrun_in_background: true{iso}\n"
                    f"prompt:\n{brief}")
        case Send(to, message):
            return f"call SendMessage\nto: {to}\nmessage:\n{message}"
        case Bash(command):
            return f"call Bash\ntimeout: {FOREGROUND_MS}\ncommand:\n{command}"
        case Stop(task_id):
            return f"call TaskStop\ntask_id: {task_id}"
        case Wait(on):
            return (f"call Bash\nrun_in_background: true\ntimeout: 7200000\ncommand:\n"
                    f"{wait_command(agent)}\n" + mctx(
                        "Then end your turn. The wait is for {on}.").format(on=on))
        case EndTurn(on, capped) if not capped:
            return mctx("End your turn with no call: the command's wait runs, for "
                        "{on}.").format(on=on)
        case EndTurn(on):
            return mctx("End your turn with no call: no wait is started, and a message or "
                        "a report of {on} wakes you.").format(on=on)
        case Again(on):
            return mctx("Run the command again: nothing is ready, and the wait is "
                        "for {on}.").format(on=on)
        case Reply(text):
            return f"final reply\n{text}"
