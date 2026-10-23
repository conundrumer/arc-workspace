"""The deferral of a change by an `Op defer:` line. No run of the change
goes on after the line, and its worktree and its editors' reports stay for
its next take, since `worktrees.worktree` takes a change's worktree as the
one its ticket's log gives.

A change no operator took (`UNTAKEN`) moves to `tickets/blocked/` at once
(`untaken`). A change the operator holds gets each of its running editors and reviewers
a message to end its commands and give its final reply, once (`held`), and
moves to `tickets/blocked/` once none of them runs. The note of that
move opens with `user` and gives `defer` (`DEFER_NOTE`).

A line defers a change only where it came after the change's last move
into its status (`taking.status_since`), so the user's word to resume the
change, which moves it to `tickets/reopened/`, ends the deferral."""

from controlled_markdown import mctx
from operations.change_agents import REVIEWER_ROLES, of_change, waiting_on
from operations.directives import Directive, numbers
from operations.handled import sent
from operations.log_commands import log
from operations.roles import EDITORS
from operations.state import State, Ticket
from operations.steps import Bash, NoStep, Send, Step
from operations.taking import moves, status_since
from ticketing.vocabulary import Kind, Status

DEFER_NOTE = mctx("user: defer")
"""The note of the line that moves a deferred change to `tickets/blocked/`."""

DEFER_WORK = mctx("Change {number} is deferred on the user's word. End your running commands "
                  "and give your final reply with what you have done and what you leave.")
"""The message to a running editor or reviewer of a change that a line defers."""

UNTAKEN = (Status.NEW, Status.APPROVED, Status.REOPENED, Status.RELEASED)
"""The statuses in which a change stands untaken, other than
`tickets/draft/`, where its ticket analyst still writes."""


def deferred_at(state: State, t: Ticket) -> float | None:
    """The time of the last `Op defer:` line to the operator that gives the
    change `t` and came after its last move into its status, or None where
    none does."""
    return max((time for n, time in numbers(state, Directive.DEFER)
                if n == t.number and time > status_since(t)), default=None)


def untaken(state: State) -> Step | None:
    """The move to `tickets/blocked/` of each untaken change a line defers,
    in one command (`taking.moves`)."""
    found = [(t, time) for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order)
             if t.kind is Kind.CHANGE and t.status in UNTAKEN
             and (time := deferred_at(state, t)) is not None]
    return moves([log(t.number, Status.BLOCKED, t.status, DEFER_NOTE, state.me) for t, _ in found],
                 f"defer {' '.join(t.number for t, _ in found)}",
                 str(max((time for _, time in found), default=0.0)))


def held(state: State, t: Ticket) -> Step | NoStep | None:
    """The next step of the change `t` that the operator holds and a line
    defers: the message to a running editor or reviewer that has none, the wait on the
    running ones, and then the move to `tickets/blocked/`. None where no
    line defers `t`."""
    time = deferred_at(state, t)
    if t.status is not Status.ASSIGNED or time is None:
        return None
    running = [a for a in of_change(state, t) if a.role in (*EDITORS, *REVIEWER_ROLES) and a.pending]
    message = DEFER_WORK.format(number=t.number)
    for a in running:
        if a.agent_id is not None and not sent(state, a.agent_id, message):
            return Send(a.agent_id, message, f"defer {t.number}", change=t.number)
    if running:
        return waiting_on(running)
    return Bash(log(t.number, Status.BLOCKED, Status.ASSIGNED, DEFER_NOTE, state.me),
                f"{t.number} defer", occasion=str(time))
