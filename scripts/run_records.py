"""The records of a run's profile: its parts, its call groups and spans,
the messages to the run, and the run itself, as the HELP of
`profile_runs` gives them."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Part(Enum):
    MODEL = "model"
    TOOLS = "tools"
    WAITS = "waits"
    IDLE = "idle"


type Key = tuple[Part, str]




@dataclass
class Group:
    time: float = 0.0
    calls: int = 0
    ran: float = 0.0


@dataclass
class Span:
    """`call` is the call's tool-use id, and `end` the time of its
    result."""
    label: str
    command: str
    start: float
    call: str
    end: float | None = None


@dataclass
class Message:
    """A message to a run: the index of its entry, its time, its text, and
    the run's `idle` time and its waits on agents before it."""
    index: int
    time: float
    text: str
    idle: float
    waits: float


@dataclass
class Run:
    label: str
    agent_type: str
    description: str
    start: float | None
    wall: float
    parts: dict[Part, float]
    groups: dict[Key, Group]
    spans: list[Span]
    in_flight: list[Span]
    backgrounded: list[Span]
    # The end of each call the run backgrounded whose end is known.
    ended: list[float]
    context: int | None
    request_contexts: list[int]
    cost: float | None
    said: str | None
    # The run's waits on agents it launched, as `profile_runs.py` HELP
    # gives them.
    waits: float
    # Whether the run waits on agents at its last entry.
    waiting: bool
    # The messages from the run's parent, the brief first, the messages
    # from other agents, and the text of each later message whose sender is
    # unknown.
    messages: list[Message]
    others: list[Message]
    unknown: list[str]
    cwd: str | None
    path: Path

    @property
    def active(self) -> float:
        return self.wall - self.parts[Part.IDLE]

    def period_end(self, i: int) -> Message | None:
        """The message that ends the period of the `i`-th message from the
        run's parent, or None where the period runs to the run's last entry."""
        m = self.messages[i]
        later = [n for n in (*self.messages[i + 1:i + 2], *self.others)
                 if n.index > m.index]
        return min(later, key=lambda n: n.index, default=None)

    def growth(self, i: int, end: Message | None, total: Callable[[Message], float],
               last: float) -> float:
        """The growth of a running total of the run over the period of the
        `i`-th message from its parent, which `end`, its `period_end`, ends:
        `total` reads the total at a message, and `last` is its value at
        the run's last entry."""
        return (last if end is None else total(end)) - total(self.messages[i])

    def active_over(self, i: int, end: Message | None) -> float | None:
        """`active_from`, with the `period_end` `end` of that period."""
        if self.start is None or self.unknown:
            return None
        return (self.growth(i, end, lambda m: m.time, self.start + self.wall)
                - self.growth(i, end, lambda m: m.idle, self.parts[Part.IDLE]))

    def active_from(self, i: int) -> float | None:
        """The active time over the period of the `i`-th message from the
        run's parent. None where its start or a message is unknown."""
        return self.active_over(i, self.period_end(i))

    def own_from(self, i: int) -> float | None:
        """The active time over the period of the `i`-th message from the
        run's parent, less the run's waits on agents over that period."""
        end = self.period_end(i)
        active = self.active_over(i, end)
        if active is None:
            return None
        return active - self.growth(i, end, lambda m: m.waits, self.waits)

    def active_at(self, now: float) -> float | None:
        """The active time of a run whose turn has not ended, over the period
        of the latest message from its parent, to `now` where that period has
        not ended: the time since its last entry goes to a pending call or
        to the model, so it is active. None where its start or that message
        is unknown."""
        return self.latest_at(now, self.active_from, True)

    def own_at(self, now: float) -> float | None:
        """`active_at`, less the run's waits on agents over that period: the
        time since its last entry is a wait where the run waits on agents at
        that entry."""
        return self.latest_at(now, self.own_from, not self.waiting)

    def latest_at(self, now: float, over: Callable[[int], float | None],
                  grows: bool) -> float | None:
        """`over` of the latest message from the run's parent, plus the time
        since the run's last entry where `grows` holds and that message's
        period has not ended."""
        if self.start is None or not self.messages:
            return None
        last = len(self.messages) - 1
        time = over(last)
        if time is None or self.period_end(last) is not None or not grows:
            return time
        return time + max(0.0, now - (self.start + self.wall))


@dataclass
class Call:
    """Where a tool call's time goes: `pending` while it is pending, and
    `background` once its result says it runs in the background."""
    pending: Key
    background: Key | None
