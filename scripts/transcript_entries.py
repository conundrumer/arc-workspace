"""Transcript timestamps and selection of lines from transcript snapshots."""

from datetime import datetime
from transcript_snapshots import Snapshot


def epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def named_lines(snap: Snapshot, own: range, naming: frozenset[str]) -> list[int]:
    """The lines of `snap` within `own` that hold a word of `naming`, in
    their order."""
    return sorted(i for i in snap.holding(naming) if i in own)


def selected_lines(snap: Snapshot, lines: range, naming: frozenset[str] | None) -> list[int]:
    """`lines` of `snap`, or with `naming` those of them that hold one of
    its words."""
    if not lines or naming is None:
        return list(lines)
    return named_lines(snap, lines, naming)
