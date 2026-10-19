"""The step journal: each Agent call, message and Bash command
(`steps.Journaled`) that `next` gave an operator of the session, under its
key (`steps.key`), from the time `next` gave it to its outcome, which `next` reads as
`scripts/operate.py --help journal` gives (`due`);
`scripts/step_journal.py` writes it and reads it back."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from controlled_markdown import mctx
from operations.command_words import is_next
from operations.constants import BACKOFF_CAP, BACKOFF_SECONDS
from operations.state import Call, Tool
from operations.steps import Journaled, Repeatable, key, retirement_key

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
    """The entries of the session's journal, in the order they were given,
    and the cuts `since` made."""
    entries: tuple[Entry, ...] = ()
    cuts: Mapping[str, float] = field(default_factory=dict[str, float])

    def since(self, cuts: Mapping[str, float]) -> "Journal":
        """The journal less each entry, of the step or retiring the step
        whose key `cuts` gives, that closed before that key's time: the
        journal as `next` reads it past the `Op override: give again` rulings
        (`directives.given_again`). An entry in flight stays, so no step in
        flight is given twice."""
        return Journal(tuple(e for e in self.entries if not cut(e, cuts)), cuts)

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


def cut(e: Entry, cuts: Mapping[str, float]) -> bool:
    """Whether `Journal.since` leaves `e` out at `cuts`."""
    return e.close is not None and any(
        k is not None and k in cuts and e.close.time < cuts[k] for k in (e.key, e.retires))


REFUSED = "Concurrent subagent limit reached"
"""The opening of the harness's refusal of an Agent call at
`constants.SUBAGENT_LIMIT`."""


def refused(e: Entry) -> bool:
    """Whether `e` failed as the harness refused its Agent call at its
    limit of concurrent subagents."""
    return (e.close is not None and e.close.outcome is Outcome.FAILED
            and e.close.why.startswith(REFUSED))


class Due(StrEnum):
    """What `next` does with a step its procedure gives."""
    GIVE = "give"
    WAIT = "wait"
    """The step is in flight, done or backing off after a refusal
    (`refused`): its procedure gives nothing in its place."""
    RETIRED = "retired"
    """The step was retired (`retired`): it is set aside, and its procedure
    read again (`order.placed`)."""
    RETIRE = "retire"
    """The step reached `BOUND`: it is retired, and its bug is filed."""


def retired(journal: Journal, key: str) -> bool:
    """Whether the command that files the bug on the step `key` was given."""
    return any(e.retires == key for e in journal.entries)


def failures(entries: Sequence[Entry]) -> list[Entry]:
    """The last of `entries`, the entries of one key, that count as times
    given in a row, as `scripts/operate.py --help journal` counts them, in
    the order they were given."""
    out: list[Entry] = []
    for e in reversed(entries):
        if e.close is None or e.close.outcome is Outcome.DONE:
            break
        if not refused(e):
            out.append(e)
    return out[::-1]


def backoff(entries: Sequence[Entry]) -> float | None:
    """The time the wait after the refusals (`refused`) that end
    `entries`, the entries of one key, ends, or None where the last of
    them is no refusal."""
    count = 0
    for e in reversed(entries):
        if not refused(e):
            break
        count += 1
    last = entries[-1].close if count else None
    if last is None:
        return None
    return last.time + min(BACKOFF_SECONDS * 2 ** (count - 1), BACKOFF_CAP)


AGAIN_LIMIT = 1
"""The number of done entries of a step given `again` past which it is
not given."""


@dataclass(frozen=True)
class Dones:
    """The done entries of one key: their count, and the time of the close
    of the last, None where there is none."""
    count: int
    last: float | None


def done_of(entries: Sequence[Entry]) -> Dones:
    closes = [e.close.time for e in entries if e.done and e.close is not None]
    return Dones(len(closes), closes[-1] if closes else None)


def due(journal: Journal, step: Journaled, now: float) -> Due:
    """What `next` does at `now` with `step`, as
    `scripts/operate.py --help journal` gives it; a step given `again` is
    given once more past its done entries, up to `AGAIN_LIMIT` of them
    (`changes.step`). Its
    failures count from the cut that lifted its retirement, where one
    did."""
    entries = journal.of(key(step))
    retiring = retirement_key(step)
    if retired(journal, retiring):
        return Due.RETIRED
    if any(e.close is None for e in entries):
        return Due.WAIT
    again = isinstance(step, Repeatable) and step.again
    if done_of(entries).count > (AGAIN_LIMIT if again else 0):
        return Due.WAIT
    if (until := backoff(entries)) is not None and now < until:
        return Due.WAIT
    lifted = journal.cuts.get(retiring)
    counted = [e for e in entries if lifted is None or e.given > lifted]
    return Due.RETIRE if len(failures(counted)) >= BOUND else Due.GIVE


def backing_off(journal: Journal, now: float) -> bool:
    """Whether a step waits at `now` after a refusal (`backoff`)."""
    keys = dict.fromkeys(e.key for e in journal.entries if e.key is not None)
    return any((until := backoff(journal.of(k))) is not None and now < until for k in keys)


def in_flight(journal: Journal, operators: Sequence[str]) -> list[Entry]:
    """The entries in flight of the operators `operators`."""
    return [e for e in journal.entries if e.close is None and e.operator in operators]


def next_call(c: Call, operator: str) -> bool:
    """Whether `c` is a call of `next` by `operator`."""
    return (c.operator == operator and c.tool == Tool.BASH
            and is_next(c.command, operator))


NOT_MADE = mctx("the operator ran `next` again before it made the call")
ENDED = mctx("the operator can no longer make the call: its work ended, or it ran `next` "
             "again first")


def closing(e: Entry, calls: Sequence[Call], live: bool, now: float) -> Close | None:
    """The outcome of `e`, an Agent call or a message in flight, at `now`,
    from `calls`, the operators' calls, where `live` is whether its
    operator may still make its call, as `scripts/operate.py --help journal`
    gives it, or None, in flight."""
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
