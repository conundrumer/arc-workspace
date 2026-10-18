"""The lines a gate run prints above its last line, and the comparison of
two output files."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import script_calls


class LineKind(StrEnum):
    """The kinds of line the last line counts."""

    DIFF = "DIFF"
    """An output file that differs."""
    SLOW = "SLOW"
    """A count of instructions grown past the accepted one, as
    `scripts/gate.py --help` gives."""


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


def slow(cmd: str, stem: str, count: int, accepted: int) -> Line | None:
    """The `SLOW` line of the command `cmd` on `stem`, whose count of
    instructions `count` compares with the accepted one `accepted`, or None
    where it did not grow past it."""
    if not script_calls.grew(count, accepted, script_calls.INSTRUCTIONS_MARGIN):
        return None
    return Line(LineKind.SLOW, cmd, stem, f"instructions={count} accepted={accepted}")


def same(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and a.read_bytes() == b.read_bytes()
