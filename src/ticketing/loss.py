"""The loss of a fault, in dollars: the priced loss of a spend, the case
line of a ticket's log that records one, and the loss rate of a ticket's
cases over the days since its first."""

import re
from collections.abc import Iterable

SECOND_PRICE = 5 / 1800
"""The dollars a second of wall time is worth: the user's preference to
count about 30 minutes saved as worth about $5 of token cost
(`prompts/agents/notes/decisions.md`, The user's preferences)."""

DAY = 86400


def loss(dollars: float, seconds: float) -> float:
    """The loss of a spend of `dollars` of tokens and `seconds` of wall
    time, in dollars."""
    return dollars + seconds * SECOND_PRICE


CASE = "case {run} {start} {end}: {dollars:.4f} dollars, {seconds:.0f} s"
"""The note of the log line that records a case."""


CASE_NOTE = re.compile(r"case (?P<run>\S+) (?P<start>\S+) (?P<end>\S+): "
                       r"(?P<dollars>[0-9.]+) dollars, (?P<seconds>[0-9]+) s")


type Found = tuple[float, float, float]
"""A case: its time, its dollars and its seconds."""


def cases(lines: Iterable[tuple[float, str]]) -> list[Found]:
    """The case of each of a ticket's log lines, given by its time and its
    note, whose note is a case line."""
    out: list[Found] = []
    for at, note in lines:
        case = CASE_NOTE.fullmatch(note)
        if case:
            out.append((at, float(case["dollars"]), float(case["seconds"])))
    return out


def per_day(total: float, first: float, now: float) -> float:
    """`total`, counted since `first`, per day up to `now`."""
    return total / (max(now - first, 1.0) / DAY)


def rate(found: Iterable[Found], now: float) -> float:
    """The summed loss of the cases `found`, which holds at least one, per
    day since the first of them."""
    found = list(found)
    return per_day(sum(loss(d, s) for _, d, s in found), min(t for t, _, _ in found), now)
