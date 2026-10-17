"""A change past its cost budget.

`change_budget` gives a change's cost budget. Once its spend passes
that budget, at the command's next call, whether or not an agent of the
change is at work, the command files the `performance` ticket on the
change that `change_budget` gives. Each agent of the change at work
before that ticket, other than its design reviewer, is told once to end
(`messages.over_budget`), and none other is launched but one item checker
on the latest report of each editor it checks (`item_check.is_checked`),
where the change has such an editor, and one design reviewer after the
latest report of each editor that builds code (`roles.BUILDERS`), where
the change has such an editor, once none is at work. Where that checker
leaves nothing for a decision, no open `question` on the change
follows the launch of the latest ticket analyst on the change, or that
analyst's hold on them is ruled `merge`, and each editor the checker does not check has
reported, and its latest report opens with `reports.DONE` or is followed
by the launch of a ticket analyst on the change, the change merges;
otherwise it moves to
`tickets/draft/` with a line that opens with `OVERRUN_FINDING`, which
`drafts` reads as findings."""

from pathlib import Path
from typing import Literal

from controlled_markdown import mctx
from operations import messages
from operations.change_agents import editors_in, latest_editors
from operations.change_budget import (OVERRUN_FINDING, by_role, file_overrun, left_draft,
                                      overrun_ticket, past_budget, taken)
from operations.change_holds import questions_hold
from operations.design_review import design_launch, open_questions
from operations.directives import Decision, decided
from operations.doc_review import with_ids
from operations.handled import sent
from operations.item_check import check_items, is_checked, unfinished
from operations.merging import merge
from operations.reports import left_for_decision
from operations.roles import BUILDERS, Role
from operations.state import Agent, State, Ticket, last_reported
from operations.steps import Bash, Launch, Send, Step, Undecided, agent_ids
from operations.log_commands import log
from ticketing.vocabulary import Status


def unreported(a: Agent, number: str) -> Undecided:
    return Undecided(mctx("{role} {agent} on change {number}, past its cost budget, returned "
                          "no report").format(role=a.role, agent=a.agent_id, number=number))


def design_left(state: State, t: Ticket, w: Path, latest: list[Agent], agents: list[Agent],
                analysts: list[Agent]) -> list[Agent] | Launch | Undecided:
    """The agents of the design review of the change `t` past its budget
    that leave it for a decision: none where no editor of `latest` builds
    code; otherwise the launch of a design reviewer where none of `agents`
    was launched after the latest report of those editors, and that
    reviewer where an open `question` on the change, an earlier reviewer's
    included, follows the launch of the latest of `analysts`, the ticket
    analysts on the change, or that analyst's hold on them
    (`questions_hold`) is not ruled `merge`, since the merge closes each
    open `question` on the change."""
    builders = [a for a in latest if a.role in BUILDERS]
    if not builders:
        return []
    built = last_reported(builders)
    reviewers = [a for a in agents if a.role is Role.DESIGN_REVIEWER and a.launched > built]
    if not reviewers:
        return design_launch(state, t, w)
    reviewer = reviewers[-1]
    if reviewer.last_report is None:
        return unreported(reviewer, t.number)
    filed = [q.filed for q in open_questions(state, t.number)]
    if not filed:
        return []
    if not analysts or max(filed) > analysts[-1].launched:
        return [reviewer]
    hold = questions_hold(analysts[-1], t.number)
    choice = decided(state, hold.text, hold.choices)
    if isinstance(choice, Undecided):
        return choice
    return [] if choice is Decision.MERGE else [reviewer]


def over_budget(state: State, t: Ticket, w: Path,
                agents: list[Agent]) -> Step | None | Literal[False]:
    """The step on the change `t` past the budget its take gives, or False
    where it is not past it or no take line gives one."""
    take_line = taken(t)
    if take_line is None:
        return False
    spent = state.computed.spent.get(t.number)
    if spent is None:
        return Undecided(mctx("the spend of change {number} since its take is unknown").format(
            number=t.number))
    if not past_budget(take_line, spent):
        return False
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
        return None
    latest = latest_editors(editors_in(agents, w))
    checked = [a for a in latest if is_checked(a)]
    leaving: list[Agent] = []
    if checked:
        reported = last_reported(checked)
        checkers = [a for a in agents if a.role is Role.ITEM_CHECKER
                    and a.launched > trip.filed and a.launched > reported]
        if not checkers:
            editors = with_ids(latest)
            if isinstance(editors, Undecided):
                return editors
            return check_items(state, t, w, latest, editors, past=trip.filed)
        checker = checkers[-1]
        if checker.last_report is None:
            return unreported(checker, t.number)
        if left_for_decision(checker) is not None:
            leaving.append(checker)
    analysts = [a for a in agents if a.role is Role.TICKET_ANALYST]
    judged = max((a.launched for a in analysts), default=0.0)
    design = design_left(state, t, w, latest, agents, analysts)
    if not isinstance(design, list):
        return design
    leaving += design
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
