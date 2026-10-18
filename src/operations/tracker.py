"""What the procedures read from a ticket's log."""

from dataclasses import dataclass
from functools import cache

from operations.state import LogLine, State, Ticket
from ticketing.exits import Exits, exit_of
from ticketing.vocabulary import COORDINATOR, WAIT_STATUSES, Domain, Kind, Status


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


@dataclass(frozen=True)
class Run:
    """A longest stretch of lines of one status in a ticket's log: the
    index of its first line, the index after its last, and the indices of
    its lines whose note opens with a wait."""
    status: Status
    start: int
    end: int
    waits: tuple[int, ...]


def run_ending(log: tuple[LogLine, ...], end: int) -> Run:
    """The run of `log` whose last line is the one before index `end`,
    where `end` is above 0."""
    status = log[end - 1].status
    start = end
    while start > 0 and log[start - 1].status is status:
        start -= 1
    return Run(status, start, end, tuple(j for j in range(start, end) if log[j].waits))


def runs(t: Ticket) -> list[Run]:
    """The runs of `t`'s log, in log order."""
    out: list[Run] = []
    end = len(t.log)
    while end > 0:
        out.append(run_ending(t.log, end))
        end = out[-1].start
    return out[::-1]


def final_run(t: Ticket) -> tuple[int, int | None]:
    """The index in `t`'s log where its final run of lines of `t`'s status
    starts, and the index of the last line of that run whose note opens
    with a wait, where one does."""
    last = run_ending(t.log, len(t.log)) if t.log else None
    if last is None or last.status is not t.status:
        return len(t.log), None
    return last.start, last.waits[-1] if last.waits else None


def wait_line(t: Ticket) -> LogLine | None:
    """The line of `t`'s log that `t` waits on, where `t` stands under
    `tickets/blocked/` or `tickets/waiting/`: the line `final_run(t)` gives
    as its last wait line."""
    if t.status not in WAIT_STATUSES:
        return None
    _, wait = final_run(t)
    return t.log[wait] if wait is not None else None


def blocked_on_user(t: Ticket) -> LogLine | None:
    """The line `wait_line(t)` gives, where `t` stands under
    `tickets/blocked/`."""
    return wait_line(t) if t.status is Status.BLOCKED else None


def closed(state: State, number: str) -> bool:
    """Whether ticket `number` stands under `tickets/closed/`. A ticket the
    read of the tracker left out (`TrackerRead.unread`) is not known to be
    closed, so what waits on it waits."""
    t = state.tracker.tickets.get(number)
    return t is not None and t.status is Status.CLOSED


def exits(state: State, t: Ticket) -> Exits:
    """`exit_of` for `t`."""
    return held_exit(t.status, t.kind, t.domain is Domain.CHANGE and not closed(state, t.subject),
                     t.title)


@cache
def held_exit(status: Status, kind: Kind, on_open_change: bool, title: str) -> Exits:
    """`exit_of`, computed once for each of its arguments in a process, as
    each read asks it again of each ticket."""
    return exit_of(status, kind, on_open_change=on_open_change, title=title)
