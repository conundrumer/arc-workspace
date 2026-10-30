"""The records of the resource daemon (`scripts/resource_daemon.py`): a
running job, and the vocabularies it uses.

Standard library only, Python 3.9."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, Optional


class Need(enum.Enum):
    """Who waits on a job's result, as the submitter declares it, and the nice value its
    processes run at. `NOW`: someone waits before the next step can start. `SOON`: the result
    feeds the next step, and nothing sits idle for it. `IDLE`: nothing waits on it."""
    NOW = "now"
    SOON = "soon"
    IDLE = "idle"

    @property
    def nice(self) -> int:
        return NICE[self]

    def raised(self, current: int) -> int:
        """The nice value of a process that runs at `current` and is given this need: its own where
        that is higher, since a user cannot lower a nice value."""
        return max(current, self.nice)


NICE = {Need.NOW: 0, Need.SOON: 5, Need.IDLE: 15}


class Kind(enum.Enum):
    """A job under a grant, or a process of a session found running without one."""
    GATED = "gated"
    UNGATED = "ungated"


@dataclass
class Job:
    """A job that counts against the machine: a gated command, whose pid is its client's, or an
    ungated process tree of a session, rooted at `pid`. `cpus` is what the gated call declares,
    and what the ungated tree uses. `start` is the start of `pid` in seconds since the epoch, which tells it from a later process of the same pid.
    `members` are the pids of the job and its descendants seen so far, each with its start
    as the process table gives it."""
    pid: int
    start: float
    owner: str
    kind: Kind
    need: Optional[Need]
    cpus: int
    command: str
    granted: float
    footprint_kib: int = 0
    peak_kib: int = 0
    cpu: float = 0.0
    members: Dict[int, float] = field(default_factory=dict)
