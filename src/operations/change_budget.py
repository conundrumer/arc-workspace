"""The cost budget of a change: the take line that gives it, the period
its spend is counted over, the test of that spend against it, and the
stop line written on a change past it.

A take writes in its log line the change's cost budget and time budget,
taken over the changes closed `fixed` before it with the same `editors`
(`scripts/spends.py`), and the cost budget is at least the dollar figure
of the Cost line of the change's Design (`Ticket.cost`). A line that
gives the held change a new `editors` field writes the budgets of that
field's set, with the same floor, which stand in place of the take's from
then on. The agents of a change are those launched since its last move
out of `tickets/draft/`, and its spend is theirs and that of the runs
under them. Once that spend passes the cost budget, the command writes
the stop line on the change. The line before a merge gives the change's
agent-running time since its take; neither time figure stops anything."""

import re
from collections.abc import Mapping
from dataclasses import replace
from typing import NamedTuple

from controlled_markdown import form
from operations.state import Budget, Spend, Ticket
from operations.log_commands import AGENT
from ticketing.vocabulary import Note, Status


BUDGET_NOTE = "budget {dollars} dollars, {seconds} s"
"""The part of a log note that gives a change's cost budget and time
budget."""

BUDGET_HOLES = {"dollars": r"(?P<dollars>[0-9.]+)", "seconds": r"(?P<seconds>[0-9]+)"}


def with_cost(b: Budget, cost: float | None) -> Budget:
    """`b` with its cost budget raised to `cost`, the dollar figure of a
    change's Cost line, where `cost` is given and above it."""
    return b if cost is None or cost <= b.dollars else replace(b, dollars=cost)


def budget_fields(b: Budget) -> dict[str, str]:
    """The values of the holes of `BUDGET_NOTE` for `b`."""
    return {"dollars": f"{b.dollars:.2f}", "seconds": f"{b.seconds:.0f}"}


TAKE_NOTE = "taking: " + BUDGET_NOTE
"""The note of the log line of a take, with the change's cost budget and
time budget."""

TAKEN = re.compile(form(TAKE_NOTE, BUDGET_HOLES))

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
    or None where no take line gives one."""
    since = left_draft(t)
    rebudget: tuple[float, float] | None = None
    for ln in reversed(t.log):
        if ln.time < since:
            break
        if rebudget is None and (m := REBUDGETED.fullmatch(ln.note)) is not None:
            rebudget = (float(m["dollars"]), ln.time)
        if (m := TAKEN.fullmatch(ln.note)) is not None:
            dollars, budgeted = (float(m["dollars"]), ln.time) if rebudget is None else rebudget
            return Take(ln.time, dollars, budgeted)
    return None


def past_budget(take: Take, spent: Spend) -> bool:
    """Whether `spent` is past the cost budget `take` gives."""
    return spent.dollars > take.dollars


def by_role(dollars: Mapping[str, float]) -> str:
    return ", ".join(f"{r} {d:.2f} dollars" for r, d in sorted(dollars.items()))


PAST_OPENING = "past its cost budget"

PAST_NOTE = PAST_OPENING + " of {limit} dollars: spent {spent} dollars, {roles}"
"""The note of the stop line, the log line that gives that a change's
spend passed its cost budget `limit`, with that spend and its part by
role."""


def past_note(limit: float, spent: Spend) -> str:
    """`PAST_NOTE` for the cost budget `limit` and the spend `spent`."""
    return PAST_NOTE.format(limit=f"{limit:.2f}", spent=f"{spent.dollars:.2f}",
                            roles=by_role(spent.by_role))


def stopped(t: Ticket) -> float | None:
    """The time of the last stop line of `t` since its last move out of
    `tickets/draft/`, or None where none stands."""
    since = left_draft(t)
    return max((ln.time for ln in t.log if ln.time >= since and ln.agent == AGENT
                and ln.note.startswith(PAST_OPENING)), default=None)


OVERRUN_FINDING = f"{Note.FINDING}: {PAST_OPENING}"
"""The opening of the note of the line that moves a change past its cost
budget to `tickets/draft/`."""
