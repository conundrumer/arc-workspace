"""The steps the command prints: each what the agent it serves does next,
a call with its parameters, the end of its turn or its final reply, and
the key of a step (`key`), as `scripts/operate.py --help next` gives it,
and its `digest`, taken over the step as given, text and all."""

import hashlib
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from controlled_markdown import mctx
from operations.constants import COORDINATOR
from operations.pacing import Pace
from operations.printed_forms import KEY_LENGTH, STEP_KEY
from operations.roles import PASSES, Model, Role
from operations.state import Agent


@dataclass(frozen=True)
class Launch:
    """An Agent call, in the background, with no isolation. `model` gives
    the call's `model` in place of the one the launch's agent document
    gives (`roles.launched_model`). `items` is the
    number of items a brief that gives several items of the same work
    gives (`briefs.ITEM_LINES`), and None for any other brief; it stays
    out of the step's key, which its brief already fixes. `reread` is the
    mark of the `Undecided` step a launch of a ticket analyst is on, and
    stays out of the step's key and its equality. `occasion` identifies
    the event the launch answers (`key`); `change` and `origin` are as
    `key` gives them."""
    role: Role
    subject: str
    brief: str
    model: Model | None = None
    items: int | None = field(default=None, repr=False)
    reread: bool = field(default=False, repr=False, compare=False)
    change: str | None = field(default=None, repr=False, compare=False)
    origin: str = field(default="", repr=False, compare=False)
    occasion: str = field(kw_only=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        given(self)


@dataclass(frozen=True)
class Send:
    """A SendMessage call. Where `since` is given, only a call an operator
    made after that time counts as made of it. `commanded` is whether `to`
    is an agent whose command reads its messages (`printed_forms.COMMANDED`); it
    stays out of the step's key and its equality, which `to` already
    fixes. `about` identifies what the message is on, among the messages its
    function sends `to`; `change`, `about` and `origin` are as `key` gives
    them."""
    to: str
    message: str
    about: str = field(repr=False)
    since: float | None = None
    commanded: bool = field(default=False, repr=False, compare=False)
    change: str | None = field(default=None, repr=False, compare=False)
    origin: str = field(default="", repr=False, compare=False)

    def __post_init__(self) -> None:
        given(self)


@dataclass(frozen=True)
class Bash:
    """A Bash command, which the command runs itself (`scripts/operate_loop.py`
    `operator_step`). `about` identifies what the command acts on, among the
    commands its function gives; `change`, `about` and `origin` are as
    `key` gives them. `occasion` identifies the event the command answers
    (`key`). `retires` is the key of the step whose retirement this command
    files the bug on (`order.retire`), or None."""
    command: str
    about: str = field(repr=False)
    change: str | None = field(default=None, repr=False, compare=False)
    origin: str = field(default="", repr=False, compare=False)
    retires: str | None = field(default=None, repr=False, compare=False)
    occasion: str = field(kw_only=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        given(self)


@dataclass(frozen=True)
class Poll:
    """Nothing is ready by the end of the command's block: the agent runs
    the command again at once. `pace` is the usage pace where it alone
    holds back an open ticket (`taking.pace_held`), or None."""
    pace: Pace | None = None


@dataclass(frozen=True)
class ListingHold:
    """A launch `launch` held for an agent type the operator's agent listing
    lacks (`order.lacked`), and `wait`, the launch of a `Role.LISTING_WAIT`
    agent whose end resumes the operator, or None where one with the key of
    `launch` as its subject is pending."""
    launch: Launch
    wait: Launch | None


@dataclass(frozen=True)
class EndTurn:
    """The agent ends its turn, and a message or the end of an agent it
    launched resumes it. With `hold`, it first makes the launch of
    `hold.wait`, where there is one, and the resume is the one that
    refreshes its agent listing."""
    hold: ListingHold | None = None


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
    such a form. `reread` is whether a reply that lands during the read of
    the state can end the hold, so the command reads the state once more
    before it launches the step's analyst (`scripts/operate_loop.py`
    `operator_step`); it stays out of the step's key and its equality.
    `change` is the number of the held change whose step it is
    (`changes.step`), which the launch of its analyst carries
    (`decisions.launch`)."""
    what: str
    given: tuple[str, ...] = field(default=(), repr=False)
    reread: bool = field(default=False, repr=False, compare=False)
    change: str | None = field(default=None, repr=False, compare=False)


UNDECIDED = "undecided:"
"""The first word of a message that gives the coordinator back a line of
its own in no form the command reads, and of a message by which an
operator in an earlier transcript gave the coordinator an undecided step
(`handled.repeated`)."""


DECISION = "for the coordinator:"
"""The opening of a message that gives the coordinator labeled items to act
on: the `decision:` items of a ticket analyst's reply, or the note of a
blocked ticket as a `decision:` item, or a change an operator hands to the
coordinator as an `unfinished:` item."""


def labeled(key: str, body: str) -> str:
    """A message to the coordinator on `key`, with the items of `body`."""
    return mctx("{label} {key}:").format(label=DECISION, key=key) + "\n" + body


def unread_line(line: str) -> Send:
    """The message that gives the coordinator back its line `line`, in no
    form the command reads."""
    return Send(COORDINATOR, mctx("{opening} a line of the coordinator's in no form the "
                                  "command reads: {line}").format(opening=UNDECIDED, line=line),
                line)


def agent_ids(agents: Iterable[Agent]) -> list[str] | Undecided:
    """The agent ids of `agents`, which a brief or a message gives, or the
    undecided step on the first of them whose id is unknown."""
    out: list[str] = []
    for a in agents:
        if a.agent_id is None:
            return Undecided(mctx("the {role} on {subject} has no known agent id").format(
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


type Journaled = Launch | Send | Bash
"""A step the journal records (`journal`)."""


def given(step: Journaled) -> None:
    """Set the `origin` of `step`, where its constructor was not given one,
    to the function that called that constructor, by its module and its
    qualified name. `dataclasses.replace` passes the origin on."""
    if not step.origin:
        caller = sys._getframe(3)
        object.__setattr__(step, "origin",
                           f"{caller.f_globals['__name__']}.{caller.f_code.co_qualname}")


def subject(step: Journaled) -> str:
    """What `step` acts on, with the event it answers: a launch's role,
    subject and `occasion`, a message's recipient, `about` and `since`, and
    a command's `about` and `occasion`."""
    match step:
        case Launch(role, on, occasion=occasion):
            return f"{role} {on} {occasion}"
        case Send(to, about=about, since=since):
            return f"{to} {about}" if since is None else f"{to} {about} {since}"
        case Bash(about=about, occasion=occasion):
            return f"{about} {occasion}"


def key(step: Step) -> str:
    """The key of `step`, which is the same at each read of the state that
    gives the same step: the key an `Override: pass over` ruling gives
    (`directives.passed_over`), and the one the journal records it under
    (`journal`). It is taken over the step's kind, its `origin` and its
    `subject`, and, for a step the journal does not record, over the step
    as given (`digest`). A solver pass's key is its task id and its
    pass, `<task id>-<pass>`, so that the writer of a ruling can form it,
    and a ruling that passes it over holds whatever overrides its brief
    gains. The key of a step whose `change` is given opens with that
    change's number, `<number>-<hash>`, so the key line `next` prints
    before it gives the change it serves (`changes.held`)."""
    if isinstance(step, Launch) and step.role in PASSES:
        return f"{step.subject}-{step.role}"
    if not isinstance(step, Launch | Send | Bash):
        return digest(step)
    named = f"{type(step).__name__} {step.origin} {subject(step)}"
    return with_change(step, hashlib.sha1(named.encode()).hexdigest()[:KEY_LENGTH])


def digest(step: Step) -> str:
    """The name of `step` as given, in the form of `key`, taken over the
    step's fields of its `repr`: two steps of one key whose texts differ
    have two digests. The files the command writes for a printed step are
    named by it (`filing`)."""
    return with_change(step, hashlib.sha1(repr(step).encode()).hexdigest()[:KEY_LENGTH])


def with_change(step: Step, digest: str) -> str:
    change = step.change if isinstance(step, Launch | Send | Bash | Undecided) else None
    return digest if change is None else f"{change}-{digest}"
