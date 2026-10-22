"""The cost budget of a change: the take line that gives it, the period
its spend is counted over, the test of that spend against it, and the
stop line written on a change past it.

A take writes in its log line the change's cost budget, in subscription
dollars, Claude and Codex together, and its time budget, taken over the
changes closed `fixed` before it with the same `editors`
(`scripts/spend_history.py`). The cost budget is at least the dollar figure
of the Cost line of the change's Design (`Ticket.cost`). A line that
gives the held change a new `editors` field writes the budgets of that
field's set, with the same floor, which stand in place of the take's from
then on. The spend of a change is that of the agents launched since its
take, and of the runs under them. Once that spend passes the cost budget, the command writes
the stop line on the change. The line before a merge gives the change's
agent-running time since its take; neither time figure stops anything."""

import re
from collections.abc import Mapping
from dataclasses import replace
from typing import NamedTuple

from controlled_markdown import form
from operations.state import Budget, Spend, UnpricedSpend, Ticket
from operations.log_commands import AGENT
from ticketing.subscription import figure
from ticketing.vocabulary import Note, Status


BUDGET_NOTE = "budget {dollars} subscription dollars, {seconds} s"
"""The part of a log note that gives a change's cost budget and time
budget."""

BUDGET_HOLES = {"dollars": r"(?P<dollars>[0-9.]+)", "seconds": r"(?P<seconds>[0-9]+)"}


def with_cost(b: Budget, cost: float | None) -> Budget:
    """`b` with its cost budget raised to `cost`, the dollar figure of a
    change's Cost line, where `cost` is given and above it."""
    return b if cost is None or cost <= b.dollars else replace(b, dollars=cost)


def budget_fields(b: Budget) -> dict[str, str]:
    """The values of the holes of `BUDGET_NOTE` for `b`."""
    return {"dollars": figure(b.dollars), "seconds": f"{b.seconds:.0f}"}


TAKE_NOTE = "taking: " + BUDGET_NOTE
"""The note of the log line of a take, with the change's cost budget and
time budget."""

TAKEN = re.compile(r"taking: .*")
TAKE_BUDGET = re.compile(form(TAKE_NOTE, BUDGET_HOLES))

EDITORS_NOTE = "editors: {editors}; " + BUDGET_NOTE
"""The note of the log line that gives a held change a new `editors`
field, with the cost budget and time budget of that field's set, which
take the place of those of its take."""

REBUDGETED = re.compile(form(EDITORS_NOTE, {"editors": r"[a-z, -]+", **BUDGET_HOLES}))


def left_draft(t: Ticket) -> float:
    """The time of the last line of `t`'s log that moves it out of
    `tickets/draft/`, or 0 where none does."""
    return max((t.log[i].time for i in range(1, len(t.log))
                if t.log[i - 1].status is Status.DRAFT and t.log[i].status is not Status.DRAFT),
               default=0.0)


TIME_OPENING = "agent-running time"

TIME_NOTE = TIME_OPENING + " {seconds:.0f} s since the take"
"""The note of the log line that gives a change's agent-running time
before its merge."""


class Take(NamedTuple):
    """What a take line gives: its time, the cost budget of the change,
    and the time of the line that gives that budget, the take line or an
    `editors` line since it."""
    time: float
    dollars: float
    budgeted: float


def taken(t: Ticket) -> Take | None:
    """The last take of `t` since its last move out of `tickets/draft/`,
    with the cost budget of the last line since that take that gives one,
    or None where no current-form budget applies to that take."""
    since = left_draft(t)
    rebudget: tuple[float, float] | None = None
    for ln in reversed(t.log):
        if ln.time < since:
            break
        if rebudget is None:
            m = REBUDGETED.fullmatch(ln.note) or TAKE_BUDGET.fullmatch(ln.note)
            if m is not None:
                rebudget = (float(m["dollars"]), ln.time)
        if TAKEN.fullmatch(ln.note) is not None:
            return Take(ln.time, *rebudget) if rebudget is not None else None
    return None


class Overrun(NamedTuple):
    """A spend past its cost budget: the limit and the spend, in subscription
    dollars."""
    limit: float
    spent: Spend | UnpricedSpend


def past_budget(take: Take, spent: Spend | UnpricedSpend) -> Overrun | None:
    """The overrun of `take`'s cost budget by `spent`, or None. The spend
    sums the known Claude and Codex dollars, so a known part that passes the
    budget alone establishes the overrun where the other is unknown."""
    return Overrun(take.dollars, spent) if spent.dollars > take.dollars else None


def by_role(dollars: Mapping[str, float]) -> str:
    return ", ".join(f"{r} {figure(d)} subscription dollars" for r, d in sorted(dollars.items()))


PAST_OPENING = "past its cost budget"

PAST_NOTE = PAST_OPENING + " of {limit} subscription dollars: spent {spent} subscription dollars, {roles}"
"""The note of the stop line, the log line that gives that a change's
spend passed its cost budget `limit`, with that spend and its part by
role."""


def past_note(overrun: Overrun) -> str:
    """The stop note for an established cost overrun."""
    spent = overrun.spent
    roles = spent.by_role if isinstance(spent, Spend) else {
        s.role: spent.codex.dollars(s.role) for s in spent.codex.sources}
    return PAST_NOTE.format(limit=figure(overrun.limit), spent=figure(spent.dollars),
                            roles=by_role(roles))


def stopped(t: Ticket) -> float | None:
    """The time of the last stop line of `t` at or after its take, or
    since its last move out of `tickets/draft/` where no take applies, or
    None where none stands."""
    take = taken(t)
    since = left_draft(t) if take is None else take.time
    return max((ln.time for ln in t.log if ln.time >= since and ln.agent == AGENT
                and ln.note.startswith(PAST_OPENING)), default=None)


OVERRUN_FINDING = f"{Note.FINDING}: {PAST_OPENING}"
"""The opening of the note of the line that moves a change past its cost
budget to `tickets/draft/`."""
