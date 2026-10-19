"""A section of the survey: its heading, whether it runs Souffle or a
solver, and the function that computes its markdown; and the parts a
section's markdown is built from."""

import datetime
import statistics
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from controlled_markdown import mctx


@dataclass(frozen=True)
class Section:
    heading: str
    level: int
    slow: bool
    """Whether it runs Souffle, `run_dl.py` or the engine."""
    compute: Callable[[], str]
    """The section's markdown, from the line after its heading to the
    line before the next heading: its definitions, its tables and items,
    then its inputs and date."""

    @property
    def name(self) -> str:
        """The name a run of the survey takes: the heading's slug."""
        return "-".join(self.heading.lower().split())


def ran(inputs: str) -> str:
    """The line that ends a section: what it read, and the date of the run
    that computed it."""
    return mctx("Inputs: {inputs}. Computed on {date}.").format(
        inputs=inputs, date=datetime.date.today().isoformat())


def table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def items(lines: Iterable[str]) -> str:
    return "\n".join(f"- {line}" for line in lines)


def body(*blocks: str) -> str:
    """Blocks of markdown, a blank line between each two."""
    return "\n\n".join(b.strip("\n") for b in blocks if b)


def quantile(xs: Sequence[int], p: int) -> int:
    """The `p`th percentile of `xs`, as the value at that rank of the
    sorted values; `p` 100 is the largest."""
    s = sorted(xs)
    return s[-1] if p >= 100 else s[min(len(s) - 1, len(s) * p // 100)]


def median(xs: Sequence[int]) -> float:
    m = statistics.median(xs)
    return int(m) if m == int(m) else m


def most(per: Mapping[str, int]) -> tuple[int, str]:
    """The largest count of `per` and the first key, in sorted order, that
    holds it."""
    key = max(sorted(per), key=lambda k: per[k])
    return per[key], key


def dist(counts: Mapping[Any, int]) -> str:
    """A distribution as `value:count` pairs in the order of the values."""
    return ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))


def named(pairs: Iterable[tuple[str, object]]) -> str:
    """Names with a count each, as `name count`, joined by commas."""
    return ", ".join(f"{k} {v}" for k, v in pairs)
