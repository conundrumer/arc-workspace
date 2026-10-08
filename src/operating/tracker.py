"""What the procedures read from a ticket's log, and the `file_ticket.py
log` calls they print, in the form `file_ticket.py log --help` gives."""

import re
import shlex
from pathlib import Path

from operating.state import LogLine, State, Ticket
from ticketing.vocabulary import COORDINATOR, Note, Status

AGENT = "operator"
"""The `<agent>` of each log line the operator writes."""

FILE_TICKET = ("uv", "run", "python", "scripts/file_ticket.py")

WORKTREE = re.compile(r"(/\S+/\.claude/worktrees/[^\s,;:)]+)")


def log(number: str, status: Status, current: Status, note: str, agent_id: str | None) -> str:
    """The Bash command that moves ticket `number` from `current` to
    `status`, or writes a line in it, with `note`."""
    args = [*FILE_TICKET, "log", number, str(status),
            AGENT, "--from", str(current)]
    if agent_id is not None:
        args += ["--id", agent_id]
    return shlex.join([*args, note])




def worktree(t: Ticket, state: State) -> Path | None:
    """The worktree the latest line of `t`'s log that gives one gives,
    where it stands, past each line whose note opens with `Note.RERUN`. A line
    that opens with `Note.RERUN` and stands after the worktree's line leaves
    none."""
    for line in reversed(t.log):
        if line.note.startswith(Note.RERUN):
            return None
        m = WORKTREE.search(line.note)
        if m is not None:
            path = Path(m[1])
            return path if path in state.worktrees else None
    return None


def last_index(t: Ticket, words: tuple[str, ...]) -> int:
    """The index of the last line of `t`'s log whose note opens with one of
    `words`, or -1."""
    for i in range(len(t.log) - 1, -1, -1):
        if t.log[i].note.startswith(words):
            return i
    return -1


def after(t: Ticket, i: int) -> tuple[LogLine, ...]:
    return t.log[i + 1:]



def coordinator_lines(lines: tuple[LogLine, ...]) -> list[LogLine]:
    """The lines of a log, or of a part of one, that the coordinator
    wrote."""
    return [ln for ln in lines if ln.agent == COORDINATOR]


def coordinator_line(t: Ticket) -> float:
    """The time of the last line of `t`'s log the coordinator wrote, or
    of its filing where it wrote none."""
    return max((ln.time for ln in coordinator_lines(t.log)), default=t.filed)


def blocked_on_user(t: Ticket) -> LogLine | None:
    """The line that moved `t` into `tickets/blocked/` waiting on the user,
    where `t` stands there for it."""
    if t.status is not Status.BLOCKED:
        return None
    for line in reversed(t.log):
        if line.status is not Status.BLOCKED:
            return None
        if line.on_user:
            return line
    return None


def closed(state: State, number: str) -> bool:
    """Whether ticket `number`, which the tracker holds, stands under
    `tickets/closed/`."""
    return state.tickets[number].status is Status.CLOSED
