"""The steps the command prints: each what the agent it serves does next,
a call with its parameters, the end of its turn or its final reply, and
the key that names a step."""

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from arc.task import TASK_ID
from controlled_markdown import mctx
from operations.constants import COORDINATOR, FOREGROUND_MS
from operations.roles import PASSES, Model, Role
from operations.state import Agent


BLOCK_SECONDS = (FOREGROUND_MS // 1000) - 30
"""The longest foreground block of the command's `next`, under the bound on
a foreground call, with room for the read of the state."""


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
    """A SendMessage call. Where `since` is given, only a call an operator
    made after that time counts as made of it."""
    to: str
    message: str
    since: float | None = None


@dataclass(frozen=True)
class Bash:
    """A Bash call in the foreground, with the timeout `FOREGROUND_MS`."""
    command: str


@dataclass(frozen=True)
class Poll:
    """Nothing is ready by the end of the command's block: the agent runs
    the command again at once."""


@dataclass(frozen=True)
class EndTurn:
    """The agent ends its turn with no call, and a message or the end of
    an agent it launched resumes it."""


@dataclass(frozen=True)
class Reply:
    """The final reply, printed once the agent sent its text to `to`, its
    parent (`final_reply.final_sends`): an agent's report is not delivered
    while an agent it resumed by SendMessage runs."""
    to: str


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
(`handled.repeated`)."""


DECISION = "for the coordinator:"
"""The opening of a message that gives the coordinator labeled items to act
on: the `decision:` items of a ticket analyst's reply, or the note of a
blocked ticket as a `decision:` item."""


def unread_line(line: str) -> Send:
    """The message that gives the coordinator back its line `line`, in no
    form the command reads."""
    return Send(COORDINATOR, mctx("{opening} a line of the coordinator's in no form the "
                                  "command reads: {line}").format(opening=UNDECIDED, line=line))


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


def rulable(text: str) -> bool:
    """Whether `text`, a step or the brief of a ticket analyst on one, gives
    the `Decision:` line that rules a step `held` made."""
    return re.search(rf"`Decision: {STEP_KEY.pattern} <choice>`", text) is not None


def held(what: str, choices: Mapping[str, str]) -> Undecided:
    """A step that holds its procedure until a `Decision:` line rules it,
    which gives its decision key and one of `choices`, each given with what
    it does."""
    given = "; ".join(f"`{c}`: {meaning}" for c, meaning in choices.items())
    return Undecided(what + mctx(". Rule it by the line `Decision: {key} <choice>`, with one "
                                 "of these choices: {given}.").format(key=decision_key(what),
                                                                      given=given))


type Step = Launch | Send | Undecided | Bash | Poll | EndTurn | Reply


def key(step: Step) -> str:
    """The key of `step`, which is the same at each read of the state that
    gives the same step: the key an `Override: pass over` ruling gives
    (`directives.passed_over`). A solver pass's key is its task id and its
    pass, `<task id>-<pass>`, so that the writer of a ruling can form it,
    and a ruling that passes it over holds whatever overrides its brief
    gains."""
    if isinstance(step, Launch) and step.role in PASSES:
        return f"{step.subject}-{step.role}"
    return hashlib.sha1(repr(step).encode()).hexdigest()[:KEY_LENGTH]


KEY_LENGTH = 12


STEP_KEY = re.compile(rf"{TASK_ID}-(?:{'|'.join(PASSES)})|[0-9a-f]{{{KEY_LENGTH}}}")
