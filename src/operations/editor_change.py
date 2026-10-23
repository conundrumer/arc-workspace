"""The change and peer reports used by an editor's review request.

`changes.editor_step` reads these inputs before selecting a review stage.
The report time is anchored to the editor's current work, as
`scripts/operate.py --help review` gives it.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from controlled_markdown import mctx
from operations.change_agents import (change_editors, editors_in, latest_editors,
                                      of_change, reported_at, unstaffed)
from operations.roles import LAUNCHING_EDITORS, Role
from operations.state import Agent, Ended, Report, State, Ticket
from operations.steps import Poll, Undecided, agent_ids
from operations.worktrees import worktree


NO_OPERATOR = mctx("{agent} is no code editor or doc editor that an operator of the session "
                   "launched: give your final reply.")
"""The line `changes.editor_step` gives an agent that is none of `LAUNCHING_EDITORS`
an operator launched."""


type Fingerprint = Callable[[Path, Path], str]
"""The fingerprint of an editor's work, given its worktree and its report
file; it raises a `ValueError` where it cannot read them."""
type Anchoring = Callable[[str, str, float], float]
"""The time an editor's work was first reviewed, given its agent id, the
fingerprint of its work and the time now."""


@dataclass(frozen=True)
class EditorChange:
    """The change `t` of the editor `editor`, with its editors `editors`,
    its worktree `w`, and its agents, the editor read as ended with its
    report at `at`."""
    editor: str
    t: Ticket
    editors: tuple[Role, ...]
    w: Path
    at: float
    agents: list[Agent]


def editor_change(state: State, editor: str, written: Callable[[Path], str | None],
                  fingerprint: Fingerprint, anchoring: Anchoring
                  ) -> EditorChange | Undecided | str:
    """The change of the editor `editor`, one of `LAUNCHING_EDITORS` an
    operator launched, with its report the text `written` gives of the
    report file its brief gives (`state.Agent.report_file`), at the time
    `anchoring` gives for the fingerprint of its work: the time of its
    first review of that work, so each later call of the command keeps that
    time while the work does not change, and a change to the work moves it
    to now.
    Only a pending editor owns the checks; after it ends, the operator
    owns them. Where the editor is none of those, or its report file is not there,
    it gives the line for that, and where its ticket, the ticket's
    editors, the change's worktree or its report file is not read, an
    `Undecided`."""
    mine = [a for a in state.transcripts.agents
            if a.agent_id == editor and a.role in LAUNCHING_EDITORS]
    if not mine:
        return NO_OPERATOR.format(agent=editor)
    if not mine[-1].pending:
        return mctx("Your work has ended, so the operator takes the change's next step: "
                    "give your final reply.")
    t = state.tracker.tickets.get(mine[-1].subject)
    if t is None:
        return Undecided(mctx("the ticket of change {number} of {role} {agent} is not "
                              "read").format(number=mine[-1].subject, role=mine[-1].role,
                                             agent=editor))
    editors = change_editors(t)
    if not isinstance(editors, tuple):
        return editors
    w = worktree(t, state)
    if w is None:
        return Undecided(mctx("change {number} gives no worktree").format(number=t.number))
    path = mine[-1].report_file
    if path is None:
        return Undecided(mctx("the brief of {role} {agent} gives no report file").format(
            role=mine[-1].role, agent=editor))
    text = written(path)
    if text is None:
        return mctx("Your report file {path} does not exist: write your report to it, then run "
                    "this command again.").format(path=path)
    try:
        at = anchoring(editor, fingerprint(w, path), state.now)
    except (ValueError, OSError) as e:
        return Undecided(mctx("the work of {role} {agent} cannot be fingerprinted: {why}").format(
            role=mine[-1].role, agent=editor, why=e))
    agents = [as_ended(a, at, text, path) if a.agent_id == editor else a
              for a in of_change(state, t)]
    return EditorChange(editor, t, editors, w, at, agents)


def as_ended(a: Agent, at: float, text: str, path: Path) -> Agent:
    """The editor `a` read as ended with the report `text` of its report
    file `path` at `at`, as `changes.editor_step` reads an editor that has
    reported."""
    report = Report(at, text, path)
    return replace(a, state=Ended(report, a.refused), reports=(*a.reports, report))


def peers_ended(c: EditorChange, written: Callable[[Path], str | None],
                fingerprint: Fingerprint) -> list[Agent] | Poll | Undecided:
    """The agents of the change `c` with each other pending editor in its
    worktree read as ended, each with the text `written` gives of its
    report file as its report at its `change_agents.reported_at` (with
    `fingerprint`, and an `Undecided` where that raises), where
    each has such a report and that of `c.editor` is the latest of theirs,
    or of the latest the one of the first agent id in sort order; and
    `steps.Poll` where one has none, another's is later, or a check another
    editor there launched is pending."""
    here = editors_in(c.agents, c.w)
    others = [a for a in here if a.pending]
    peers = {a.agent_id for a in here} - {c.editor}
    if any(a.pending and a.operator in peers for a in c.agents):
        return Poll()
    if not others:
        return c.agents
    other_ids = agent_ids(others)
    if isinstance(other_ids, Undecided):
        return other_ids
    times = [(-c.at, c.editor)]
    ended: dict[str, Agent] = {}
    for a, i in zip(others, other_ids, strict=True):
        try:
            since = reported_at(a, c.w, fingerprint)
        except (ValueError, OSError) as e:
            return Undecided(mctx("the work of {role} {agent} cannot be fingerprinted: {why}").format(
                role=a.role, agent=i, why=e))
        other_text = None if a.report_file is None else written(a.report_file)
        if since is None or a.report_file is None or other_text is None:
            return Poll()
        times.append((-since, i))
        ended[i] = as_ended(a, since, other_text, a.report_file)
    if min(times) != (-c.at, c.editor):
        return Poll()
    return [ended.get(a.agent_id or "", a) for a in c.agents]


def handed_on(state: State, c: EditorChange) -> str | None:
    """The line that has the editor of the change `c` give its final reply
    as the operator takes the change's next step: where an editor role of
    the change has no agent in its worktree or another editor there ended
    with no report since its launch or its last resume; or None."""
    here = editors_in(c.agents, c.w)
    if unstaffed(c.editors, here) or any(a.unreported for a in latest_editors(here)):
        return mctx("Another editor of change {number} has not reported, so the operator "
                    "takes its next step: give your final reply.").format(
                        number=c.t.number)
    return None


