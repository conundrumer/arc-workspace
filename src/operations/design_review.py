"""The design review of a change with an editor that builds code
(`roles.BUILDERS`): an agent other than its editors judges the design of
the built change against `master` before the change merges.

A change gets one design reviewer per revision: one after its last move
out of `tickets/draft/`, and one more after each rebase conflict in a path
that is no document (`merging.CONFLICT_OPENING`), once an editor of the
change has reported after that conflict, so that the reviewer judges the
resolution against the `master` the change was rebased onto. The
reviewer's findings are the `question` tickets on the change
(`open_questions`), which `changes.leftover` hands to a ticket analyst."""

from pathlib import Path
from typing import Literal

from controlled_markdown import mctx
from operations import briefs
from operations.change_agents import settled
from operations.change_budget import left_draft
from operations.filing import editor_scratch
from operations.merging import CONFLICT_OPENING, DOCUMENT_SUFFIX, conflict_note_paths
from operations.roles import BUILDERS, Role
from operations.state import Agent, State, Ticket
from operations.steps import Launch, Step, Undecided
from ticketing.times import utc_stamp
from ticketing.vocabulary import Domain, Kind, Status


def open_questions(state: State, number: str) -> list[Ticket]:
    """The open `question` tickets filed on the change `number`."""
    return [q for q in state.tracker.tickets.values() if q.kind is Kind.QUESTION
            and q.domain is Domain.CHANGE and q.subject == number
            and q.status in (Status.OPEN, Status.ASSIGNED)]


def code_conflicts(t: Ticket) -> list[float] | Undecided:
    """The times of the lines of `t`'s log that give a rebase conflict in a
    path that is no document."""
    times: list[float] = []
    for ln in t.log:
        if not ln.note.startswith(CONFLICT_OPENING):
            continue
        paths = conflict_note_paths(ln.note)
        if not paths:
            return Undecided(mctx("the `conflict` line of change {number} at {time} gives no "
                                  "path in the form the operator reads").format(
                                      number=t.number, time=utc_stamp(ln.time)))
        if any(not p.endswith(DOCUMENT_SUFFIX) for p in paths):
            times.append(ln.time)
    return times


def due_since(t: Ticket, here: list[Agent]) -> float | None | Undecided:
    """The time after which the change `t`, whose editors in its worktree
    are `here`, needs a design reviewer launched, or None where it needs
    none yet, as after a conflict that no editor has reported on since."""
    since = left_draft(t)
    conflicts = code_conflicts(t)
    if isinstance(conflicts, Undecided):
        return conflicts
    conflict = max(conflicts, default=since)
    if conflict <= since:
        return since
    if any((r := a.last_report) is not None and r.time > conflict for a in here):
        return conflict
    return None


def builds_code(editors: tuple[Role, ...]) -> bool:
    return any(r in BUILDERS for r in editors)


def design_review(state: State, t: Ticket, w: Path, editors: tuple[Role, ...],
                  here: list[Agent], agents: list[Agent]) -> Step | Literal[False]:
    """The launch of the design reviewer of the change `t`, whose editors
    are `editors`, those in its worktree `w` `here`, and whose agents, those
    of other sessions included, are `agents`, or False where none is due or
    the one due is at work or has reported. A reviewer that ended with no
    report holds the change, since the merge waits on its judgment."""
    if not builds_code(editors):
        return False
    since = due_since(t, here)
    if isinstance(since, Undecided):
        return since
    if since is None:
        return False
    reviewers = [a for a in agents if a.role is Role.DESIGN_REVIEWER and a.launched > since]
    if not reviewers:
        return design_launch(state, t, w)
    last = reviewers[-1]
    if last.pending or last.last_report is not None:
        return False
    return Undecided(mctx("design reviewer {agent} on change {number} ended with no "
                          "report").format(agent=last.agent_id, number=t.number))


def reviewing(agents: list[Agent]) -> bool:
    """Whether a design reviewer among `agents` is at work, which holds the
    merge."""
    return any(a.pending for a in agents if a.role is Role.DESIGN_REVIEWER)


def design_launch(state: State, t: Ticket, w: Path) -> Launch:
    """The launch of a design reviewer on the change `t` in its worktree
    `w`, keyed as an editor's launch is."""
    return Launch(Role.DESIGN_REVIEWER, t.number, briefs.design_review(
        t.number, w, editor_scratch(t.number, Role.DESIGN_REVIEWER, state.scratch), state.me,
        settled(state, t, Role.DESIGN_REVIEWER, None)),
        occasion=f"{w} {t.last_time}")
