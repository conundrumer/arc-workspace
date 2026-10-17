"""The step journal: each Agent call, message and Bash command
(`steps.Journaled`) that `next` gave an operator of the session, under its
key (`steps.key`), from the time `next` gave it to its outcome, which `next` reads as
`scripts/operate.py --help journal` gives (`due`);
`scripts/step_journal.py` writes it and reads it back."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from controlled_markdown import mctx
from operations.command_words import is_next
from operations.state import Call, Tool

BOUND = 3
"""How many times in a row a step is given before it is retired."""


class Outcome(StrEnum):
    """How a step of the journal ended."""
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class Close:
    """The outcome of a step, at `time`, with the first line of why it
    failed, empty for a step done."""
    outcome: Outcome
    time: float
    why: str


@dataclass(frozen=True)
class Entry:
    """A step `next` gave the operator `operator` at `given`: its key, its
    digest (`steps.digest`) and its origin (`steps.Launch.origin`), the
    tool of its call, a message's recipient, the message, the command or
    the launch's description (`roles.description`), the key of the step
    whose retirement the command files its bug on (`steps.Bash.retires`),
    the change it serves (`steps.Launch.change`), and its outcome, None
    while it is in flight. `key` is None for a
    message seeded from a SendMessage call an operator made before the
    journal of its session was started (`scripts/step_journal.py`)."""
    key: str | None
    digest: str
    origin: str
    operator: str
    given: float
    tool: Tool
    to: str | None
    text: str
    retires: str | None
    change: str | None
    close: Close | None

    @property
    def done(self) -> bool:
        return self.close is not None and self.close.outcome is Outcome.DONE


@dataclass(frozen=True)
class Journal:
    """The entries of the session's journal, in the order they were given."""
    entries: tuple[Entry, ...] = ()

    def of(self, key: str) -> list[Entry]:
        return [e for e in self.entries if e.key == key]

    def sent(self, to: str) -> list[Entry]:
        """The messages to `to` that are done, in the order they were
        given."""
        return [e for e in self.entries if e.tool is Tool.SEND_MESSAGE and e.to == to and e.done]

    def retiring(self, operator: str) -> list[Entry]:
        """The commands that filed the bug on a retired step, of those
        given to `operator`."""
        return [e for e in self.entries if e.retires is not None and e.operator == operator]


class Due(StrEnum):
    """What `next` does with a step its procedure gives."""
    GIVE = "give"
    WAIT = "wait"
    """The step is in flight, done or retired: its procedure gives nothing
    in its place."""
    RETIRE = "retire"
    """The step reached `BOUND`: it is retired, and its bug is filed."""


def retired(journal: Journal, key: str) -> bool:
    """Whether the command that files the bug on the step `key` was given."""
    return any(e.retires == key for e in journal.entries)


def in_row(entries: Sequence[Entry]) -> int:
    """How many of the last of `entries`, the entries of one key, count as
    times given in a row, as `scripts/operate.py --help journal` counts
    them: those that failed, since the last that was done."""
    count = 0
    for e in reversed(entries):
        if e.close is None or e.close.outcome is Outcome.DONE:
            break
        count += 1
    return count


def due(journal: Journal, key: str) -> Due:
    """What `next` does with the step `key`."""
    entries = journal.of(key)
    if retired(journal, key) or any(e.close is None or e.done for e in entries):
        return Due.WAIT
    return Due.RETIRE if in_row(entries) >= BOUND else Due.GIVE


def in_flight(journal: Journal, operators: Sequence[str]) -> list[Entry]:
    """The entries in flight of the operators `operators`."""
    return [e for e in journal.entries if e.close is None and e.operator in operators]


def next_call(c: Call, operator: str) -> bool:
    """Whether `c` is a call of `next` by `operator`."""
    return (c.operator == operator and c.tool == Tool.BASH
            and is_next(str(c.input.get("command", "")), operator))


NOT_MADE = mctx("the operator ran `next` again before it made the call")
ENDED = mctx("the operator can no longer make the call: its work ended, or it ran `next` "
             "again first")


def closing(e: Entry, calls: Sequence[Call], live: bool, now: float) -> Close | None:
    """The outcome of `e`, an Agent call or a message in flight, at `now`,
    from `calls`, the operators' calls, where `live` is whether its
    operator may still make its call: the outcome of that operator's call
    of the step, an Agent call that gives the launch's description or a
    SendMessage call to its recipient, made after `next` gave it and before its
    next call of `next`; failed where that call of `next` came first, or
    where no such call came and the operator may make it no longer; and
    None, in flight, otherwise."""
    after = sorted((c for c in calls if c.operator == e.operator and c.time > e.given),
                   key=lambda c: c.time)
    nexts = [c for c in after if next_call(c, e.operator)]
    bound = nexts[0].time if nexts else None
    made = [c for c in after if (bound is None or c.time < bound) and makes(e, c)]
    if made:
        c = made[0]
        if c.result is None:
            return None
        if c.error:
            lines = c.result.strip().splitlines()
            return Close(Outcome.FAILED, c.time, lines[0] if lines else "")
        return Close(Outcome.DONE, c.time, "")
    if bound is not None:
        return Close(Outcome.FAILED, bound, NOT_MADE)
    return None if live else Close(Outcome.FAILED, now, ENDED)


def makes(e: Entry, c: Call) -> bool:
    """Whether `c` is a call of the step `e`."""
    match e.tool:
        case Tool.SEND_MESSAGE:
            return (c.tool == Tool.SEND_MESSAGE and c.input.get("to") == e.to
                    and e.text.strip() in c.message)
        case Tool.AGENT:
            return c.tool == Tool.AGENT and c.input.get("description") == e.text
        case _:
            return False
