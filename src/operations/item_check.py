"""The launch of an item checker on a change: the latest reports of the
editors it checks, what the agents before it settled
(`change_agents.settled`), and the accepted gate outputs it reads. No item checker checks the `UNCHECKED` editor,
whose report goes to the ticket analyst on what the editors leave where
it leaves items unfinished (`unfinished`)."""

from pathlib import Path

from controlled_markdown import mctx
from gating.commands import Command, command_of
from operations import briefs
from operations.change_agents import change_editors, settled
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


def checked_outputs(t: Ticket, outputs: tuple[str, ...]) -> list[str] | Undecided:
    """The accepted gate outputs of `outputs`, those the change `t` writes,
    whose diff an item checker reads: on a change with the `UNCHECKED`
    editor, those of no `run_dl.py` command (`Command`), whose diff that
    editor's part can cause, so that no checker judges that part's
    outputs."""
    roles = change_editors(t)
    if isinstance(roles, Undecided):
        return roles
    if UNCHECKED not in roles:
        return list(outputs)
    kept: list[str] = []
    for path in outputs:
        cmd = command_of(path)
        if cmd is None:
            return Undecided(mctx("the accepted gate output {path} that change {number} "
                                  "writes is the output of no gate command").format(
                                      path=path, number=t.number))
        if not isinstance(cmd, Command):
            kept.append(path)
    return kept


def latest_reports(agents: list[Agent]) -> list[tuple[str, str]] | Undecided:
    """The agent id and latest report text of each of `agents` that has a
    report."""
    reporting = [(a, r) for a in agents if (r := a.last_report) is not None]
    reporters = agent_ids(a for a, _ in reporting)
    if isinstance(reporters, Undecided):
        return reporters
    return [(i, r.text) for i, (_, r) in zip(reporters, reporting, strict=True)]


def check_items(state: State, t: Ticket, w: Path, needing: list[Agent],
                editors: list[tuple[Agent, str]], past: float | None = None) -> Step:
    """The launch of an item checker on the latest reports of the editors
    `needing` it checks (`is_checked`), which have reported since the last
    item checker was launched on the change `t`, and on the accepted gate
    outputs of `checked_outputs`, with each editor of `editors` it checks,
    and what the agents before it settled (`change_agents.settled`).
    `past` gives the time the overrun ticket of the change was filed,
    where the change is past its cost budget, so that a checker launched
    before the overrun does not take its step key."""
    reports = latest_reports([a for a in needing if is_checked(a)])
    if isinstance(reports, Undecided):
        return reports
    gate = checked_outputs(t, state.held.gate_outputs.get(w, ()))
    if isinstance(gate, Undecided):
        return gate
    occasion = last_reported(needing)
    if past is not None:
        occasion = max(occasion, past)
    return Launch(Role.ITEM_CHECKER, t.number, briefs.item_check(
        t.number, w, reports, gate, [(a, i) for a, i in editors if is_checked(a)], state.me,
        settled(state, t, Role.ITEM_CHECKER, None), past is not None), occasion=str(occasion))
