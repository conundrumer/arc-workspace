"""The steps the command prints: each the one call the operator agent makes
next, with its parameters in full, and the text that prints it."""

import hashlib
import shlex
from dataclasses import dataclass

from controlled_markdown import mctx
from operating.roles import Role, description
from operating.state import State

COORDINATOR = "main"
"""The address SendMessage reaches the coordinator at."""

WAIT_SECONDS = 240
"""The longest wait in the background: the interval of the keep-alive
timer it replaces (`agent_timer.KEEP_ALIVE_SECONDS`)."""

WAIT_CAP = 11
"""How many waits in a row may end on `WAIT_SECONDS` with no message, no
report and no step between them, as the section `keep-alive-timer` of
`prompts/agents/notes/commands.md` caps the keep-alive timer."""

FOREGROUND_MS = 240000
"""The timeout of a foreground Bash call the command prints: the bound
`scripts/pending_wait_hook.py` holds a subagent's foreground call to."""


@dataclass(frozen=True)
class Launch:
    """An Agent call, in the background. `worktree` gives the Agent tool's
    `isolation: "worktree"`."""
    role: Role
    subject: str
    brief: str
    worktree: bool = False


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

DECISION = "decision for the user:"
"""The opening of a message that gives the coordinator a decision a ticket
analyst brings the user."""


def undecided(what: str) -> Send:
    """A step the command cannot place, given to the coordinator. The
    command reads back that it was sent by its text, so `what` is the same
    at each read of the same state."""
    return Send(COORDINATOR, f"{UNDECIDED} {what}")


type Step = Launch | Send | Bash | Stop | Wait | EndTurn | Again | Reply


def repeated(step: Step, state: State) -> bool:
    """Whether `step` is a message an operator already sent: a step whose
    procedure then waits on its answer."""
    return isinstance(step, Send) and state.sent(step.to, step.message)


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


def pass_over(command: str) -> tuple[str, str] | None:
    """The key and the line of a call of `operate.py pass-over`, or None
    for any other command."""
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    head = [*RUN_COMMAND.split(), PASS_OVER]
    if words[:len(head)] != head or len(words) != len(head) + 3:
        return None
    return words[-2], words[-1]


def passed(step: Step, state: State) -> str | None:
    """The line by which an operator passed `step` over, or None."""
    return state.passed.get(key(step))


def wait_command(agent: str) -> str:
    return (f": 'unattended-wait: operate.py wait'; "
            f"{RUN_COMMAND} wait {agent}")


def next_command(agent: str) -> str:
    return f"{RUN_COMMAND} next {agent}"


def printed(step: Step, agent: str) -> str:
    """The text the command prints for `step`, for the operator whose agent
    id is `agent`."""
    match step:
        case Launch(role, subject, brief, worktree):
            iso = '\nisolation: "worktree"' if worktree else ""
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
