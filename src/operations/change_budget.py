"""The cost budget of a change: the take line that gives it, the period
its spend is counted over, the test of that spend against it, and the
`performance` ticket filed on a change past it.

A take writes in its log line the change's cost budget and time budget,
taken over the changes closed `fixed` before it with the same `editors`
(`scripts/spends.py`). A line that gives the held change a new
`editors` field writes the budgets of that field's set, which stand in
place of the take's from then on. The agents of a change are those launched
since its last move out of `tickets/draft/`, and its spend is theirs and
that of the runs under them. Once that spend passes the cost budget, the
command files a `performance` ticket on the change, on the agent type
whose spend most exceeds its median over those changes. The line before a
merge gives the change's agent-running time since its take; neither time
figure stops anything."""

import re
import shlex
from collections.abc import Mapping
from typing import NamedTuple

from controlled_markdown import form, mctx
from operations.state import Agent, Budget, Spend, State, Ticket
from operations.steps import Bash, Step
from operations.log_commands import AGENT, FILE_TICKET
from ticketing.text import ticket_text
from ticketing.vocabulary import DEFECT_SECTIONS, Domain, Kind, Note, Status


BUDGET_NOTE = "budget {dollars} dollars, {seconds} s"
"""The part of a log note that gives a change's cost budget and time
budget."""

BUDGET_HOLES = {"dollars": r"(?P<dollars>[0-9.]+)", "seconds": r"(?P<seconds>[0-9]+)"}


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


def overrun_ticket(state: State, t: Ticket, since: float) -> Ticket | None:
    """The `performance` ticket an operator filed on the change `t` at or
    after `since`."""
    return next((p for p in sorted(state.tracker.tickets.values(), key=lambda p: p.order)
                 if p.kind is Kind.PERFORMANCE and p.domain is Domain.CHANGE
                 and p.subject == t.number and p.filer == AGENT and p.filed >= since), None)


def at_fault(spent: Spend, budget: Budget) -> str:
    """The agent type whose spend most exceeds its median spend over the
    changes the budget is taken over; an agent type with no median spent
    nothing on them (ticket 6-634)."""
    return max(sorted(spent.by_role),
               key=lambda r: spent.by_role[r] - budget.role_medians.get(r, 0.0))


def by_role(dollars: Mapping[str, float]) -> str:
    return ", ".join(f"{r} {d:.2f} dollars" for r, d in sorted(dollars.items()))


def file_overrun(t: Ticket, spent: Spend, budget: Budget, limit: float,
                 agents: list[Agent]) -> Step:
    """The command that files the `performance` ticket on the change `t`
    past its cost budget `limit`, on the agent type at fault."""
    role = at_fault(spent, budget)
    ids = [a.agent_id for a in agents if a.role.agent_type == role and a.agent_id is not None]
    title = mctx("change {number}: {role} spent most over its usual spend, past the change's "
                 "cost budget").format(number=t.number, role=role)
    impact, evidence = DEFECT_SECTIONS
    text = ticket_text(Kind.PERFORMANCE, title, {
        impact: mctx("Change {number} spent {spent} dollars, past its cost budget of {limit} "
                     "dollars, and its work in flight ended.").format(
                         number=t.number, spent=f"{spent.dollars:.2f}", limit=f"{limit:.2f}"),
        evidence: "\n".join([
            mctx("Spend by role: {spend}.").format(spend=by_role(spent.by_role)),
            mctx("Median spend by role over the changes the budget is taken over: "
                 "{medians}.").format(medians=by_role(budget.role_medians)),
            mctx("Agents of {role} on the change: {ids}.").format(
                role=role, ids=", ".join(ids) or "none")])})
    return Bash(shlex.join([*FILE_TICKET, Domain.CHANGE.value, t.number, AGENT])
                + " <<'TICKET'\n" + text + "TICKET", f"{t.number} past its budget", occasion=str(t.last_time))


OVERRUN_FINDING = f"{Note.FINDING}: past its cost budget"
"""The opening of the note of the line that moves a change past its cost
budget to `tickets/draft/`."""
