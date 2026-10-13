"""The launch of an item checker on a change: the latest reports of its
editors, the replies of its ticket analysts, and the accepted gate
outputs the change writes."""

from pathlib import Path

from operations import briefs
from operations.change_agents import of_change
from operations.roles import Role
from operations.state import Agent, State, Ticket
from operations.steps import Launch, Step, Undecided, agent_ids


def latest_reports(agents: list[Agent]) -> list[tuple[str, str]] | Undecided:
    """The agent id and latest report text of each of `agents` that has a
    report."""
    reporting = [(a, r) for a in agents if (r := a.last_report) is not None]
    reporters = agent_ids(a for a, _ in reporting)
    if isinstance(reporters, Undecided):
        return reporters
    return [(i, r.text) for i, (_, r) in zip(reporters, reporting, strict=True)]


def check_items(state: State, t: Ticket, w: Path, needing: list[Agent],
                editors: list[tuple[Agent, str]], past: bool = False) -> Step:
    """The launch of an item checker on the latest reports of the editors
    `needing`, which have reported since the last item checker was launched
    on the change `t`, and on the accepted gate outputs the change writes,
    with the latest report of each ticket analyst launched on `t` that has
    reported, in launch order, so the checker leaves out what they already
    decided. `past` gives that the change is past its cost budget."""
    reports = latest_reports(needing)
    if isinstance(reports, Undecided):
        return reports
    decisions = [(a.agent_id, r.text) for a in of_change(state, t.number)
                 if a.role is Role.TICKET_ANALYST and a.agent_id is not None
                 and (r := a.last_report) is not None]
    return Launch(Role.ITEM_CHECKER, t.number, briefs.item_check(
        t.number, w, reports, decisions, list(state.held.gate_outputs.get(w, ())), editors, state.me,
        past))
