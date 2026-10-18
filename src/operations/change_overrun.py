"""A change past its cost budget.

`change_budget` gives a change's cost budget. Once its spend passes
that budget, at the command's next call, whether or not an agent of the
change is at work, the command files the `performance` ticket on the
change that `change_budget` gives. Each agent of the change at work
before that ticket, other than its design reviewer, is told once to end
(`messages.over_budget`). Once none is at work, the change moves to
`tickets/draft/` with a line that opens with `OVERRUN_FINDING`, which
`drafts` reads as findings, where its worktree holds no work
(`worktrees.holds_work`), or where an editor gave no report, or none
after it was told to end, so that no edit no report gives merges.
Otherwise none is launched but one item checker on the latest report of
each editor it checks (`item_check.is_checked`), where the change has
such an editor and no item checker was launched after that report, and
the design reviewer `design_review` gives due, by the rule that holds
within the budget; then the step is `Ended`, on which `changes.leftover` gives what those
agents leave to one ticket analyst, whose brief gives the change past its
cost budget, and the change merges with the work its worktree holds."""

from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from operations import messages
from operations.change_agents import change_editors, editors_in, latest_editors
from operations.change_budget import (OVERRUN_FINDING, by_role, file_overrun, left_draft,
                                      overrun_ticket, past_budget, taken)
from operations.design_review import design_review
from operations.doc_review import with_ids
from operations.handled import sent, sent_at
from operations.item_check import check_items, is_checked
from operations.roles import Role
from operations.state import Agent, Spend, State, Ticket, last_reported
from operations.steps import Bash, Pause, Send, Step, Undecided, agent_ids
from operations.log_commands import log
from operations.worktrees import holds_work
from ticketing.vocabulary import Status


@dataclass(frozen=True)
class Ended:
    """A change past its budget whose agents told to end have reported,
    whose item checker and design reviewer, where it has them, reported
    after its `latest` editors, and whose worktree holds work."""
    latest: tuple[Agent, ...]


def unreported(a: Agent, number: str) -> Undecided:
    return Undecided(mctx("{role} {agent} on change {number}, past its cost budget, returned "
                          "no report").format(role=a.role, agent=a.agent_id, number=number))


def to_draft(state: State, t: Ticket, limit: float, spent: Spend, case: str,
             occasion: float) -> Bash:
    """The move of the change `t` past its budget `limit` to
    `tickets/draft/`, with its spend `spent` and the `case` that moves it."""
    return Bash(log(t.number, Status.DRAFT, Status.ASSIGNED, mctx(
        "{opening} of {limit} dollars: spent {spent} dollars, {roles}; {case}").format(
            opening=OVERRUN_FINDING, limit=f"{limit:.2f}", spent=f"{spent.dollars:.2f}",
            roles=by_role(spent.by_role), case=case),
        state.me), f"{t.number} overrun", occasion=str(occasion))


def silent(state: State, t: Ticket, latest: list[Agent]) -> tuple[list[Agent], float]:
    """The editors of `latest` that gave no report, or that were told to
    end (`messages.over_budget`) and gave no report after the latest such
    message, and the time of the latest message to them, or 0 where none
    was told."""
    out: list[Agent] = []
    told = 0.0
    message = messages.over_budget(t.number, False)
    for a in latest:
        times = sent_at(state, a.agent_id, message) if a.agent_id is not None else []
        if (r := a.last_report) is None or (times and r.time <= max(times)):
            out.append(a)
            told = max(told, *times) if times else told
    return out, told


def over_budget(state: State, t: Ticket, w: Path,
                agents: list[Agent]) -> Step | Ended | Pause:
    """The step on the change `t` past the budget its take gives, `Ended`
    where what its agents leave goes to `changes.leftover`, or
    `Pause.CLEAR` where it is not past it or no take line gives one."""
    take_line = taken(t)
    if take_line is None:
        return Pause.CLEAR
    spent = state.computed.spent.get(t.number)
    if spent is None:
        return Undecided(mctx("the spend of change {number} since its take is unknown").format(
            number=t.number))
    if not past_budget(take_line, spent):
        return Pause.CLEAR
    limit = take_line.dollars
    trip = overrun_ticket(state, t, left_draft(t))
    if trip is None:
        budget = state.computed.budgets.get(t.number)
        if budget is None:
            return Undecided(mctx("the median spend by role of the changes the budget of "
                                  "change {number} is taken over is unknown").format(
                                      number=t.number))
        return file_overrun(t, spent, budget, limit, agents)
    for a in agents:
        if a.pending and a.agent_id is not None and a.launched < trip.filed \
                and a.role is not Role.DESIGN_REVIEWER:
            message = messages.over_budget(t.number, a.role is Role.DOC_REVIEWER)
            if not sent(state, a.agent_id, message):
                return Send(a.agent_id, message, f"over budget {t.number}")
    if any(a.pending for a in agents):
        return Pause.WAIT
    here = editors_in(agents, w)
    latest = latest_editors(here)
    if not holds_work(w):
        return to_draft(state, t, limit, spent, mctx(
            "its worktree holds no change against `master` and no untracked file git "
            "does not ignore"),
            max(trip.filed, last_reported(latest)))
    quiet, told = silent(state, t, latest)
    if quiet:
        ids = agent_ids(quiet)
        if isinstance(ids, Undecided):
            return ids
        return to_draft(state, t, limit, spent, mctx(
            "each of {agents} gave no report, or none after it was told to end").format(
                agents=", ".join(ids)), max(told, trip.filed))
    checked = [a for a in latest if is_checked(a)]
    if checked:
        reported = last_reported(checked)
        checkers = [a for a in agents if a.role is Role.ITEM_CHECKER and a.launched > reported]
        if not checkers:
            editors = with_ids(latest)
            if isinstance(editors, Undecided):
                return editors
            return check_items(state, t, w, latest, editors, state.me, past=trip.filed)
        if checkers[-1].unreported:
            return unreported(checkers[-1], t.number)
    roles = change_editors(t)
    if isinstance(roles, Undecided):
        return roles
    if (step := design_review(state, t, w, roles, here, agents, state.me)) is not False:
        return Pause.WAIT if step is None else step
    return Ended(tuple(latest))
