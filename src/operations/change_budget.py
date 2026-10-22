"""The cost budget of a change: the take line that gives it, the period
its spend is counted over, the test of that spend against it, and the
stop line written on a change past it.

A take writes in its log line the change's cost budget and time budget,
taken over the changes closed `fixed` before it with the same `editors`
(`scripts/spend_history.py`). The dollar budget is at least the dollar figure
of the Cost line of the change's Design (`Ticket.cost`); raising that budget
raises its Codex token budget by the same factor. A line that
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
from operations.state import Budget, CodexSpend, Spend, UnpricedSpend, Ticket
from operations.log_commands import AGENT
from ticketing.vocabulary import Note, Status


BUDGET_NOTE = "budget {dollars} dollars, {codex} Codex tokens, {seconds} s"
"""The part of a log note that gives a change's cost budget and time
budget."""

BUDGET_HOLES = {"dollars": r"(?P<dollars>[0-9.]+)", "seconds": r"(?P<seconds>[0-9]+)",
                "codex": r"(?P<codex>[0-9]+|none)"}


def with_cost(b: Budget, cost: float | None) -> Budget:
    """`b` with its cost budget raised to `cost`, the dollar figure of a
    change's Cost line, where `cost` is given and above it."""
    if cost is None or cost <= b.dollars:
        return b
    if b.codex_tokens is None or b.dollars == 0:
        return replace(b, dollars=cost)
    return replace(b, dollars=cost, codex_tokens=round(b.codex_tokens * cost / b.dollars))


def budget_fields(b: Budget) -> dict[str, str]:
    """The values of the holes of `BUDGET_NOTE` for `b`."""
    return {"dollars": f"{b.dollars:.2f}", "seconds": f"{b.seconds:.0f}",
            "codex": str(b.codex_tokens) if b.codex_tokens is not None else "none"}


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
    codex_tokens: int | None


def taken(t: Ticket) -> Take | None:
    """The last take of `t` since its last move out of `tickets/draft/`,
    with the cost budget of the last line since that take that gives one,
    or None where no current-form budget applies to that take."""
    since = left_draft(t)
    rebudget: tuple[float, float, int | None] | None = None
    for ln in reversed(t.log):
        if ln.time < since:
            break
        if rebudget is None:
            m = REBUDGETED.fullmatch(ln.note) or TAKE_BUDGET.fullmatch(ln.note)
            if m is not None:
                rebudget = (float(m["dollars"]), ln.time,
                            None if m["codex"] == "none" else int(m["codex"]))
        if TAKEN.fullmatch(ln.note) is not None:
            return Take(ln.time, *rebudget) if rebudget is not None else None
    return None


class DollarOverrun(NamedTuple):
    limit: float
    spent: Spend


class TokenOverrun(NamedTuple):
    limit: int
    spent: CodexSpend


type Overrun = DollarOverrun | TokenOverrun


def past_budget(take: Take, spent: Spend | UnpricedSpend) -> Overrun | None:
    """An independently measured cost component past its limit, if any."""
    if isinstance(spent, Spend) and spent.dollars > take.dollars:
        return DollarOverrun(take.dollars, spent)
    if spent.codex is not None and take.codex_tokens is not None:
        tokens = spent.codex.totals().total_tokens
        if tokens is not None and tokens > take.codex_tokens:
            return TokenOverrun(take.codex_tokens, spent.codex)
    return None


def by_role(dollars: Mapping[str, float]) -> str:
    return ", ".join(f"{r} {d:.2f} dollars" for r, d in sorted(dollars.items()))


PAST_OPENING = "past its cost budget"

PAST_NOTE = PAST_OPENING + " of {limit} {unit}: spent {spent} {unit}, {roles}"
"""The note of the stop line, the log line that gives that a change's
spend passed its cost budget `limit`, with that spend and its part by
role."""


def past_note(overrun: Overrun) -> str:
    """The stop note for an established cost overrun."""
    if isinstance(overrun, DollarOverrun):
        return PAST_NOTE.format(limit=f"{overrun.limit:.2f}",
                                spent=f"{overrun.spent.dollars:.2f}", unit="dollars",
                                roles=by_role(overrun.spent.by_role))
    codex = overrun.spent
    roles = ", ".join(f"{role} {codex.totals(role).total_tokens} Codex tokens"
                      for role in sorted({s.role for s in codex.sources})
                      if codex.totals(role).total_tokens is not None)
    return PAST_NOTE.format(limit=overrun.limit, spent=codex.totals().total_tokens,
                            unit="Codex tokens", roles=roles)


def stopped(t: Ticket) -> float | None:
    """The time of the last stop line of `t` since its last move out of
    `tickets/draft/`, or None where none stands."""
    since = left_draft(t)
    return max((ln.time for ln in t.log if ln.time >= since and ln.agent == AGENT
                and ln.note.startswith(PAST_OPENING)), default=None)


OVERRUN_FINDING = f"{Note.FINDING}: {PAST_OPENING}"
"""The opening of the note of the line that moves a change past its cost
budget to `tickets/draft/`."""
