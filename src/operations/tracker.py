"""What the procedures read from a ticket's log, and the `file_ticket.py
log` calls they print, in the form `file_ticket.py log --help` gives;
`fingerprint` gives the state of the worktree that log gives a change."""

import hashlib
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from engine import checkout

from operations.roles import Role
from operations.state import LogLine, State, Ticket
from ticketing.vocabulary import COORDINATOR, Note, Status

AGENT = Role.OPERATOR.value
"""The `<agent>` of each log line the operator writes."""

FILE_TICKET = ("uv", "run", "python", "scripts/file_ticket.py")

BASE = "master"
"""The branch a change's worktree branches from and merges into."""

WORKTREES = ".claude/worktrees"
"""The directory, under the main tree, of the worktrees of changes."""

WORKTREE = re.compile(rf"(/\S+/{re.escape(WORKTREES)}/[^\s,;:)]+)")


def log(number: str, status: Status, current: Status, note: str, agent_id: str | None) -> str:
    """The Bash command that moves ticket `number` from `current` to
    `status`, or writes a line in it, with `note`."""
    args = [*FILE_TICKET, "log", number, str(status),
            AGENT, "--from", str(current)]
    if agent_id is not None:
        args += ["--id", agent_id]
    return shlex.join([*args, note])


def add_editor(number: str, editor: Role, agent_id: str) -> str:
    """The Bash command that adds `editor` to the `editors` field of the
    change `number` that `agent_id` holds."""
    return shlex.join([*FILE_TICKET, "editors", number, str(editor), AGENT, agent_id])




def logged_worktree(t: Ticket) -> Path | None:
    """The worktree the latest line of `t`'s log that gives one gives,
    past each line whose note opens with `rerun`. A line whose note opens
    with `rerun` and stands after the worktree's line leaves none."""
    for line in reversed(t.log):
        if line.note.startswith(Note.RERUN):
            return None
        m = WORKTREE.search(line.note)
        if m is not None:
            return Path(m[1])
    return None


def fingerprint(w: Path) -> str:
    """What `scripts/change_worktree.py --fingerprint w` prints, as its
    `--help` gives it."""
    digest = hashlib.sha256(checkout.git_out(w, "diff", "--merge-base", BASE,
                                             "--binary").encode())
    for rel in sorted(checkout.untracked(w)):
        digest.update(rel.encode() + b"\0")
        digest.update((w / rel).read_bytes() + b"\0")
    return digest.hexdigest()


def worktree(t: Ticket, state: State) -> Path | None:
    """`logged_worktree` of `t`, where it stands."""
    return worktree_in(t, state.git.worktrees)


def worktree_in(t: Ticket, worktrees: frozenset[Path]) -> Path | None:
    """`logged_worktree` of `t`, where it is among `worktrees`."""
    path = logged_worktree(t)
    return path if path in worktrees else None


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


SET_ASIDE = (Status.DEFERRED, Status.BLOCKED)
"""The statuses a move into `tickets/open/` from gives a ticket to a fresh
ticket analyst."""


def reopened_line(t: Ticket) -> float:
    """The time of the last line of `t`'s log that leaves it `open` where
    the line before it left it in one of `SET_ASIDE`, or of its filing
    where no line does."""
    return max((ln.time for before, ln in zip(t.log, t.log[1:])
                if ln.status is Status.OPEN and before.status in SET_ASIDE), default=t.filed)


@dataclass(frozen=True)
class Run:
    """A longest stretch of lines of one status in a ticket's log: the
    index of its first line, the index after its last, and the indices of
    its lines whose note opens with a wait."""
    status: Status
    start: int
    end: int
    waits: tuple[int, ...]


def runs(t: Ticket) -> list[Run]:
    """The runs of `t`'s log, in log order."""
    out: list[Run] = []
    start = 0
    for i in range(1, len(t.log) + 1):
        if i == len(t.log) or t.log[i].status is not t.log[start].status:
            out.append(Run(t.log[start].status, start, i,
                           tuple(j for j in range(start, i) if t.log[j].waits)))
            start = i
    return out


def final_run(t: Ticket) -> tuple[int, int | None]:
    """The index in `t`'s log where its final run of lines of `t`'s status
    starts, and the index of the last line of that run whose note opens
    with a wait, where one does."""
    last = runs(t)[-1:]
    if not last or last[0].status is not t.status:
        return len(t.log), None
    return last[0].start, last[0].waits[-1] if last[0].waits else None


def wait_line(t: Ticket) -> LogLine | None:
    """The line of `t`'s log that `t` waits on, where `t` stands under
    `tickets/blocked/`: the line `final_run(t)` gives as its last wait
    line."""
    if t.status is not Status.BLOCKED:
        return None
    _, wait = final_run(t)
    return t.log[wait] if wait is not None else None


def blocked_on_user(t: Ticket) -> LogLine | None:
    """The line `wait_line(t)` gives, where that wait is on the user."""
    line = wait_line(t)
    return line if line is not None and line.on_user else None


def closed(state: State, number: str) -> bool:
    """Whether ticket `number` stands under `tickets/closed/`. A ticket the
    read of the tracker left out (`TrackerRead.unread`) is not known to be
    closed, so what waits on it waits."""
    t = state.tracker.tickets.get(number)
    return t is not None and t.status is Status.CLOSED
