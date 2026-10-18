"""The design review of a change with an editor that builds code
(`roles.BUILDERS`): an agent other than its editors judges the design of
the built change against `master` before the change merges.

A change gets one design reviewer per revision: one after its last move
out of `tickets/draft/`, and one more after each rebase conflict in a path
that is no document (`merging.CONFLICT_OPENING`), once an editor of the
change has reported after that conflict, so that the reviewer judges the
resolution against the `master` the change was rebased onto. The
reviewer's findings are the `question` tickets on the change
(`change_holds.open_questions`), which `changes.leftover` hands to a ticket analyst."""

from pathlib import Path

from controlled_markdown import mctx
from operations import briefs
from operations.change_agents import latest_of_role, settled, worktree_occasion
from operations.change_budget import left_draft
from operations.filing import editor_scratch
from operations.merging import CONFLICT_OPENING, conflict_note_paths, documents_only
from operations.roles import BUILDERS, Role
from operations.state import Agent, State, Ticket
from operations.steps import Launch, Pause, Step, Undecided
from ticketing.times import utc_stamp


def code_conflicts(t: Ticket) -> list[float] | Undecided:
    times: list[float] = []
    for ln in t.log:
        if not ln.note.startswith(CONFLICT_OPENING):
            continue
        paths = conflict_note_paths(ln.note)
        if not paths:
            return Undecided(mctx("the `conflict` line of change {number} at {time} gives no "
                                  "path in the form the operator reads").format(
                                      number=t.number, time=utc_stamp(ln.time)))
        if not documents_only(paths):
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
                  here: list[Agent], agents: list[Agent], launcher: str) -> Step | Pause:
    """The launch by `launcher` of the design reviewer of the change `t`,
    whose editors are `editors`, those in its worktree `w` `here`, and
    whose agents, those of other sessions and those its editors launched
    included, are `agents`, or `Pause.CLEAR` where none is due or
    the one due is at work or has reported. A reviewer that ended with no
    report holds the change, since the merge waits on its judgment."""
    if not builds_code(editors):
        return Pause.CLEAR
    since = due_since(t, here)
    if isinstance(since, Undecided):
        return since
    if since is None:
        return Pause.CLEAR
    step = latest_of_role(agents, Role.DESIGN_REVIEWER, since, t.number,
                          lambda: design_launch(state, t, w, launcher))
    return Pause.CLEAR if step is None else step


def reviewing(agents: list[Agent]) -> bool:
    """Whether a design reviewer among `agents` is at work, which holds the
    merge."""
    return any(a.pending for a in agents if a.role is Role.DESIGN_REVIEWER)


def design_launch(state: State, t: Ticket, w: Path, launcher: str) -> Launch:
    """The launch by `launcher` of a design reviewer on the change `t` in
    its worktree `w`."""
    return Launch(Role.DESIGN_REVIEWER, t.number, briefs.design_review(
        t.number, w, editor_scratch(t.number, Role.DESIGN_REVIEWER, state.scratch), launcher,
        settled(state, t, Role.DESIGN_REVIEWER, None)),
        occasion=worktree_occasion(t, w))
