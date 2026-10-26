"""The launch of an item checker on a change: the latest reports of the
editors it checks, what the agents before it settled
(`change_agents.settled`), and its
round (`check_round`). No item checker checks the `UNCHECKED` editor,
whose report goes to the ticket analyst on what the editors leave where
it leaves items unfinished (`unfinished`)."""

from pathlib import Path

from operations import briefs
from operations.change_agents import of_roles_since_draft, settled
from operations.constants import REVIEW_ROUNDS
from operations.completion import occupies
from operations.reports import done
from operations.roles import Role
from operations.state import Agent, State, Ticket, last_reported
from operations.steps import Launch, Step, Undecided, agent_ids

UNCHECKED = Role.HANDBOOK_EXPANDED
"""The editor no item checker checks: the handbook judges its part, the
lib and the solvers, and the item checker's context holds no handbook."""


def is_checked(editor: Agent) -> bool:
    """Whether an item checker checks the items of `editor`."""
    return editor.role is not UNCHECKED


def unfinished(editors: list[Agent], since: float) -> list[Agent]:
    """The editors of `editors` no item checker checks whose latest
    report, given after `since`, does not open with `reports.DONE`, and so
    leaves items for a decision."""
    return [a for a in editors if not is_checked(a) and (r := a.last_report) is not None
            and r.time > since and not done(a)]


def check_round(state: State, t: Ticket) -> briefs.Round:
    """The round of the launch of an item checker on the change `t`. The
    round of a launch is one more than the count of item checkers that
    still run or reported their result on `t` since its last move out of `tickets/draft/`, those of other
    sessions included: `REVIEW_ROUNDS` is its last round, and each launch
    after it is the check after the cap. The cap of another kind of review
    ends no round of the item check, so the decided edits at that cap get
    the next round."""
    launched = sum(occupies(a) for a in of_roles_since_draft(state, t, (Role.ITEM_CHECKER,)))
    if launched >= REVIEW_ROUNDS:
        return briefs.Round.AFTER_CAP
    return briefs.Round.LAST if launched + 1 == REVIEW_ROUNDS else briefs.Round.OPEN


def latest_reports(agents: list[Agent]) -> list[tuple[str, str]] | Undecided:
    """The agent id and latest report text of each of `agents` that has a
    report."""
    reporting = [(a, r) for a in agents if (r := a.last_report) is not None]
    reporters = agent_ids(a for a, _ in reporting)
    if isinstance(reporters, Undecided):
        return reporters
    return [(i, r.text) for i, (_, r) in zip(reporters, reporting, strict=True)]


def check_items(state: State, t: Ticket, w: Path, needing: list[Agent],
                editors: list[tuple[Agent, str]], launcher: str) -> Step:
    """The launch by `launcher` of an item checker on the latest reports of the editors
    `needing` it checks (`is_checked`), which have reported since the last
    item checker was launched on the change `t`, with each editor of
    `editors` it checks, and what the agents before it settled (`change_agents.settled`)."""
    reports = latest_reports([a for a in needing if is_checked(a)])
    if isinstance(reports, Undecided):
        return reports
    occasion = last_reported(needing)
    return Launch(Role.ITEM_CHECKER, t.number, briefs.item_check(
        t.number, w, reports, [(a, i) for a, i in editors if is_checked(a)], launcher,
        settled(state, t, Role.ITEM_CHECKER, None), check_round(state, t)),
        occasion=str(occasion))
