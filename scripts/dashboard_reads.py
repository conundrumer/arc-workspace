"""The reads the ticket dashboard (`ticket_dashboard`) renders from: the
recorded state of the main session's operator, the spend and the estimated
cost of the changes, the links between tickets, the trend of the tracker,
the first sentence of a ticket's stated impact, and a ticket's values as
the search gives them (`Entry`)."""

import time
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from idle_sessions import named_main
from spends import Unknown, budget, recorded_spend
from state_assembly import Shown, shown_read
from ticket_form import section, section_head
from tree_reads import scratch

from operations.state import Spend, Ticket
from operations.tracker import wait_line
from ticketing.vocabulary import Kind, Status

AFTER_DECISION = 7.0
"""A change's spend after its decision, in dollars, as
`prompts/agents/notes/decisions.md#cost-and-time` gives it."""

IMPACT = "Impact"
SAVING_KINDS = (Kind.BUG, Kind.PERFORMANCE, Kind.DELAY)
"""The kinds whose open tickets the page gives as bugs and cost savings,
with the first sentence of their `## Impact` section."""

OPEN = frozenset(Status) - {Status.CLOSED, Status.DRAFT}
DAY = 86400.0
TREND_DAYS = 14


def operator_state(tickets: Path) -> Shown | str:
    """The state the last read of the main session's operator recorded
    (`state_assembly.write_shown`), or why there is none."""
    session = named_main(tickets)
    if session is None:
        return "no main session is set (`file_ticket.py main`)"
    return shown_read(scratch(session))


def first_sentence(text: str) -> str:
    """The first sentence of `text`, its whitespace runs each one space."""
    body = " ".join(text.split())
    end = body.find(". ")
    return body if end < 0 else body[:end + 1]


def impact(t: Ticket) -> str:
    """The first sentence of the `## Impact` section of `t`'s file."""
    try:
        text = t.path.read_text()
    except OSError:
        return ""
    if section_head(text, IMPACT) is None:
        return ""
    return first_sentence(section(text, IMPACT))


@dataclass(frozen=True)
class Costs:
    """The spend of each closed change that has a record, and the estimated
    cost of each other change, in dollars, with the roles each counts."""
    spent: dict[str, Spend]
    estimated: dict[str, tuple[float, tuple[str, ...]] | None]


def costs(tickets: Path, all_: Mapping[str, Ticket], now: float, undecided: list[str]) -> Costs:
    spent: dict[str, Spend] = {}
    estimated: dict[str, tuple[float, tuple[str, ...]] | None] = {}
    budgets: dict[frozenset[str], tuple[float, tuple[str, ...]] | None] = {}
    for n, t in all_.items():
        if t.kind is not Kind.CHANGE:
            continue
        if t.status is Status.CLOSED:
            r = recorded_spend(t.path)
            if r is not None and r is not Unknown.SPEND:
                spent[n] = r
            continue
        if t.editors is None:
            estimated[n] = None
            continue
        key = frozenset(t.editors)
        if key not in budgets:
            b = budget(tickets, frozenset(t.editors), now, undecided)
            budgets[key] = None if b is None else (b.dollars + AFTER_DECISION,
                                                   tuple(sorted(b.role_medians)))
        estimated[n] = budgets[key]
    return Costs(spent, estimated)


def served_by(all_: Mapping[str, Ticket]) -> dict[str, list[str]]:
    """The changes whose Motivation gives each ticket, in the tracker's
    order."""
    out: dict[str, list[str]] = {}
    for n, t in sorted(all_.items(), key=lambda kv: kv[1].order):
        if t.kind is Kind.CHANGE:
            for m in t.motivation:
                if n not in out.setdefault(m, []):
                    out[m].append(n)
    return out


def waits_on(t: Ticket) -> list[str]:
    """The tickets `t` waits on: the change of its wait line and its
    `depends-on` field."""
    line = wait_line(t)
    first = [line.on_change] if line is not None and line.on_change is not None else []
    return list(dict.fromkeys([*first, *t.depends_on]))


def status_at(t: Ticket, at: float) -> Status | None:
    held = [ln.status for ln in t.log if ln.time <= at]
    return held[-1] if held else None


def trend(all_: Iterable[Ticket], now: float) -> list[tuple[str, int, int, int]]:
    """For each of the last `TREND_DAYS` days (UTC), the tickets filed, the
    moves into `tickets/closed/`, and the open tickets at its end."""
    today = now - now % DAY
    days = [today - i * DAY for i in range(TREND_DAYS - 1, -1, -1)]
    filed: Counter[float] = Counter()
    closed: Counter[float] = Counter()
    open_at: Counter[float] = Counter()
    for t in all_:
        filed[t.filed - t.filed % DAY] += 1
        for ln in t.log:
            if ln.status is Status.CLOSED:
                closed[ln.time - ln.time % DAY] += 1
        for d in days:
            if status_at(t, min(now, d + DAY)) in OPEN:
                open_at[d] += 1
    return [(time.strftime("%m-%d", time.gmtime(d)), filed[d], closed[d], open_at[d]) for d in days]


@dataclass(frozen=True)
class Entry:
    """A ticket as the search gives it: the tickets it waits on and that
    wait on it, the changes that serve it, its estimated cost in dollars,
    whether a watch prices its gain, and the text of its cost, empty for a
    ticket that is no change and is not open."""
    ticket: Ticket
    waits_on: tuple[str, ...]
    waited_by: tuple[str, ...]
    served_by: tuple[str, ...]
    estimate: float | None
    priced: bool
    cost: str
