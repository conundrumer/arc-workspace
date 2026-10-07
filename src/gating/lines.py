"""The lines a gate run prints above its last line, and the comparison of
two output files."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class LineKind(StrEnum):
    """The kinds of line the last line counts."""

    DIFF = "DIFF"
    """An output file that differs."""
    SLOW = "SLOW"
    """A time over the accepted one, where the outside CPU is at most one
    core."""
    LOADED = "LOADED"
    """A time over the accepted one, where the outside CPU is over one
    core."""
    NOTIME = "NOTIME"
    """A time with no accepted time it is compared with, as
    `scripts/gate.py --help` gives."""


TIME_KINDS = frozenset({LineKind.SLOW, LineKind.LOADED, LineKind.NOTIME})
"""The kinds of line that judge a time."""


@dataclass(frozen=True)
class Line:
    """A line the gate prints above the last line: its kind, the command,
    the stem, and what follows them."""
    kind: LineKind
    cmd: str
    stem: str
    rest: str

    def __str__(self) -> str:
        return f"{self.kind} {self.cmd} {self.stem} {self.rest}"


def same(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and a.read_bytes() == b.read_bytes()
