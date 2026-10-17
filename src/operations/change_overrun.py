"""A change past its cost budget.

`change_budget` gives a change's cost budget. Once its spend passes
that budget, at the command's next call, whether or not an agent of the
change is at work, the command files the `performance` ticket on the
change that `change_budget` gives. Each agent of the change at work
before that ticket is told once to end (`messages.over_budget`), and none
other is launched but one item checker on the latest report of each
editor it checks (`item_check.is_checked`), once none is at work, where
the change has such an editor. Where that checker leaves nothing for a
decision, and each editor it does not check has reported, and its
latest report opens with `reports.DONE` or is followed by the launch of
a ticket analyst on the change, the change merges; otherwise it moves to
`tickets/draft/` with a line that opens with `OVERRUN_FINDING`, which
`drafts` reads as findings."""

from pathlib import Path
from typing import Literal

from controlled_markdown import mctx
from operations import messages
from operations.change_agents import editors_in, latest_editors
from operations.change_budget import (OVERRUN_FINDING, by_role, file_overrun, left_draft,
                                      overrun_ticket, past_budget, taken)
from operations.doc_review import with_ids
from operations.handled import sent
from operations.item_check import check_items, is_checked, unfinished
from operations.merging import merge
from operations.reports import left_for_decision
from operations.roles import Role
from operations.state import Agent, State, Ticket, last_reported
from operations.steps import Bash, Send, Step, Undecided, agent_ids
from operations.log_commands import log
from ticketing.vocabulary import Status


def over_budget(state: State, t: Ticket, w: Path,
                agents: list[Agent]) -> Step | None | Literal[False]:
    """The step on the change `t` past the budget its take gives, or False
    where it is not past it or no take gives a budget."""
    take_line = taken(t)
    if take_line is None:
        return False
    _, limit, _ = take_line
    spent = state.computed.spent.get(t.number)
    if spent is None:
        return Undecided(mctx("the spend of change {number} since its take is unknown").format(
            number=t.number))
    if not past_budget(take_line, spent):
        return False
    trip = overrun_ticket(state, t, left_draft(t))
    if trip is None:
        budget = state.computed.budgets.get(t.number)
        if budget is None:
            return Undecided(mctx("the median spend by role of the changes the budget of "
                                  "change {number} is taken over is unknown").format(
                                      number=t.number))
        return file_overrun(t, spent, budget, limit, agents)
    for a in agents:
        if a.pending and a.agent_id is not None and a.launched < trip.filed:
            message = messages.over_budget(t.number, a.role is Role.DOC_REVIEWER)
            if not sent(state, a.agent_id, message):
                return Send(a.agent_id, message, f"over budget {t.number}")
    if any(a.pending for a in agents):
        return None
    latest = latest_editors(editors_in(agents, w))
    checked = [a for a in latest if is_checked(a)]
    leaving: list[Agent] = []
    if checked:
        reported = max((r.time for a in checked if (r := a.last_report) is not None),
                       default=0.0)
        checkers = [a for a in agents if a.role is Role.ITEM_CHECKER
                    and a.launched > trip.filed and a.launched > reported]
        if not checkers:
            editors = with_ids(latest)
            if isinstance(editors, Undecided):
                return editors
            return check_items(state, t, w, latest, editors, past=True)
        checker = checkers[-1]
        if checker.last_report is None:
            return Undecided(mctx("item checker {agent} on change {number}, past its cost "
                                  "budget, returned no report").format(agent=checker.agent_id,
                                                                       number=t.number))
        if left_for_decision(checker) is not None:
            leaving.append(checker)
    judged = max((a.launched for a in agents if a.role is Role.TICKET_ANALYST), default=0.0)
    leaving += [a for a in latest if not is_checked(a) and a.last_report is None]
    leaving += unfinished(latest, judged)
    if not leaving:
        return merge(state, t, w, latest)
    ids = agent_ids(leaving)
    if isinstance(ids, Undecided):
        return ids
    return Bash(log(t.number, Status.DRAFT, Status.ASSIGNED, mctx(
        "{opening} of {limit} dollars: spent {spent} dollars, {roles}; the latest report of "
        "each of {agents} leaves items for a decision").format(
            opening=OVERRUN_FINDING, limit=f"{limit:.2f}", spent=f"{spent.dollars:.2f}",
            roles=by_role(spent.by_role), agents=", ".join(ids)),
        state.me), f"{t.number} overrun", occasion=str(last_reported(leaving)))
