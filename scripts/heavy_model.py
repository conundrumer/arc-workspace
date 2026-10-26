"""The records of the resource daemon (`scripts/resource_daemon.py`): a
request for a share, a running job, and the vocabularies they use.

Standard library only, Python 3.9."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, Optional



class Need(enum.Enum):
    """Who waits on a job's result, as the submitter declares it. `NOW`: someone waits before
    the next step can start. `SOON`: the result feeds the next step, and nothing sits idle for
    it. `IDLE`: nothing waits on it."""
    NOW = "now"
    SOON = "soon"
    IDLE = "idle"

    @property
    def rank(self) -> int:
        """0 for the need that goes first."""
        return NEEDS.index(self)


NEEDS = [Need.NOW, Need.SOON, Need.IDLE]


class Lane(enum.Enum):
    """A short job (at most `SHORT_MINUTES` declared) waits in the short queue, any other
    in the long queue."""
    SHORT = "short"
    LONG = "long"


class Kind(enum.Enum):
    """A job under a grant, or a process of a session found running without one."""
    GATED = "gated"
    UNGATED = "ungated"


@dataclass(frozen=True)
class Amount:
    """CPUs and GiB."""
    cpus: int
    gib: int

    def __add__(self, other: Amount) -> Amount:
        return Amount(self.cpus + other.cpus, self.gib + other.gib)

    def __sub__(self, other: Amount) -> Amount:
        return Amount(self.cpus - other.cpus, self.gib - other.gib)

    def within(self, limit: Amount) -> bool:
        return self.cpus <= limit.cpus and self.gib <= limit.gib


@dataclass
class Waiter:
    """A request that waits for its share. `deadline` is the wall-clock time at which the
    client gives up, or None. `asked_cpus` and `asked_gib` are what the call gave, None where
    it gave none, from which `ask` is cut."""
    id: int
    pid: int
    start: int
    owner: str
    need: Need
    ask: Amount
    minutes: float
    command: str
    arrived: float
    deadline: Optional[float]
    asked_cpus: Optional[int] = None
    asked_gib: Optional[int] = None

    @property
    def lane(self) -> Lane:
        return lane_of(self.minutes)


@dataclass
class Job:
    """A job that holds a share: a gated command, whose pid is its client's, or an ungated
    process tree of a session, rooted at `pid`, that counts against the budget by what it
    uses. `start` is the start of `pid` in seconds since the epoch, which tells it from a later process of the same pid.
    `members` are the pids of the job and its descendants seen so far, each with its start
    as the process table gives it."""
    pid: int
    start: float
    owner: str
    kind: Kind
    need: Optional[Need]
    amount: Amount
    minutes: Optional[float]
    command: str
    granted: float
    footprint_kib: int = 0
    peak_kib: int = 0
    cpu: float = 0.0
    members: Dict[int, float] = field(default_factory=dict)

    @property
    def ends(self) -> Optional[float]:
        """The wall-clock time at which the job's declared minutes run out."""
        return None if self.minutes is None else self.granted + self.minutes * 60

    @property
    def lane(self) -> Lane:
        return lane_of(self.minutes)


SHORT_MINUTES = 5


def lane_of(minutes: Optional[float]) -> Lane:
    return Lane.SHORT if minutes is not None and minutes <= SHORT_MINUTES else Lane.LONG
