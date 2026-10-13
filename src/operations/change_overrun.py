"""A change past its cost budget, and an editor of a change whose budget
is passed.

`change_budget` gives a change's cost budget. Once its spend passes
that budget, at the command's next call, whether or not an agent of the
change is at work, the command files the `performance` ticket on the
change that `change_budget` gives. Each agent of the change at work
before that ticket is told once to end (`messages.over_budget`), and none
other is launched but one item checker on each editor's latest report,
once none is at work. Where that checker leaves nothing for a decision,
the change merges; otherwise it moves to `tickets/draft/` with a line
that opens with `OVERRUN_FINDING`, which `drafts` reads as findings.

An editor whose latest reply says its budget is passed is sent a message
to go on with the work that reply leaves, with the budget the operators
last gave it, and that reply goes to no ticket analyst."""

from pathlib import Path
from typing import Literal

from controlled_markdown import mctx
from operations import brief_reading, messages
from operations.change_agents import editors_in, latest_editors
from operations.change_budget import (OVERRUN_FINDING, by_role, file_overrun, overrun_ticket,
                                      past_budget, taken)
from operations.doc_review import with_ids
from operations.handled import sends_to, sent
from operations.item_check import check_items
from operations.merging import merge
from operations.reports import budget_passed, left_for_decision
from operations.roles import Role
from operations.state import Agent, State, Ticket
from operations.steps import Bash, Send, Step, Undecided
from operations.log_commands import log
from ticketing.vocabulary import Status


def over_budget(state: State, t: Ticket, w: Path,
                agents: list[Agent]) -> Step | None | Literal[False]:
    """The step on the change `t` past the budget its take gives, or False
    where it is not past it or no take gives a budget."""
    take_line = taken(t)
    if take_line is None:
        return False
    since, limit, _ = take_line
    spent = state.computed.spent.get(t.number)
    if spent is None:
        return Undecided(mctx("the spend of change {number} since its take is unknown").format(
            number=t.number))
    if not past_budget(take_line, spent):
        return False
    trip = overrun_ticket(state, t, since)
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
                return Send(a.agent_id, message)
    if any(a.pending for a in agents):
        return None
    latest = latest_editors(editors_in(agents, w))
    reported = max((r.time for a in latest if (r := a.last_report) is not None), default=0.0)
    checkers = [a for a in agents if a.role is Role.ITEM_CHECKER
                and a.launched > trip.filed and a.launched > reported]
    if not checkers:
        editors = with_ids(latest)
        if isinstance(editors, Undecided):
            return editors
        return check_items(state, t, w, latest, editors, past=True)
    checker = checkers[-1]
    if checker.last_report is None:
        return Undecided(mctx("item checker {agent} on change {number}, past its cost budget, "
                              "returned no report").format(agent=checker.agent_id,
                                                          number=t.number))
    if left_for_decision(checker) is None:
        return merge(state, t, w, latest)
    return Bash(log(t.number, Status.DRAFT, Status.ASSIGNED, mctx(
        "{opening} of {limit} dollars: spent {spent} dollars, {roles}; item checker {agent} "
        "leaves items for a decision").format(
            opening=OVERRUN_FINDING, limit=f"{limit:.2f}", spent=f"{spent.dollars:.2f}",
            roles=by_role(spent.by_role), agent=checker.agent_id), state.me))


def over_budget_step(state: State, t: Ticket, latest: list[Agent]) -> Step | None:
    """The message to the first editor of `latest` whose latest reply says
    its budget is passed, or None where no such reply is."""
    for a in latest:
        r = a.last_report
        if r is None or a.agent_id is None or not budget_passed(a):
            continue
        given = [a.brief] + [c.message for c in sends_to(state, a.agent_id)]
        stated = next((s for text in reversed(given) if (s := brief_reading.budgets(text))), set[float]())
        if len(stated) != 1:
            return Undecided(mctx("editor {agent} of change {number} says its budget is "
                                  "passed, and the latest brief or operator's message to it "
                                  "that states a budget states {count}").format(
                agent=a.agent_id, number=t.number, count=len(stated)))
        return Send(a.agent_id, messages.go_on(r.time, stated.pop()))
    return None
