"""What takes a ticket out of each status (`exit_of`), and the event that
frees a ticket for a fresh ticket analyst (`freed`).

The `match` in `exit_of` ends in `assert_never`, so a `Status` added with no
case fails pyright, and each case gives `frees` as well as
its exits, so a status added with no value for it fails as one with no
exit does."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, assert_never

from ticketing.vocabulary import COORDINATOR, MANY_IDEAS, Kind, Status


class Exit(StrEnum):
    """A step that takes a ticket out of its status."""
    TICKET_REVIEW = "ticket review"
    TAKE = "take"
    TICKET_ANALYST = "ticket analyst"
    MERGE = "merge"
    """The merge of a change that touches the module a `refactor` ticket on
    many ideas in one place cites."""
    CHANGE_ANALYST = "change analyst"
    """The ticket analyst of the open change a `question` is on."""
    HOLDER = "holder"
    RELEASE = "release"
    """The move to `tickets/released/` once the holder is not live."""
    COORDINATOR_MOVE = "coordinator move"
    """The coordinator's own move of a ticket that no procedure moves: a
    `request` the coordinator routes to `tickets/draft/`."""
    COORDINATOR_LINE = "coordinator line"
    MERGE_LINE = "merge line"
    """A coordinator's `Op merge:` line."""
    CHANGE_CLOSE = "change close"
    SWEEP = "sweep"


@dataclass(frozen=True)
class Exits:
    """The steps that take a ticket out of its status, and whether its move
    from that status into `tickets/reopened/` frees it for a fresh ticket
    analyst: an analyst launched before it was set aside judged it as it
    stood then."""
    by: frozenset[Exit]
    frees: bool


def exit_of(status: Status, kind: Kind, *, on_open_change: bool, title: str) -> Exits:
    """The exits of a ticket of `kind` in `status`, with `title`.
    `on_open_change`: its subject is a change not closed."""
    change = kind is Kind.CHANGE
    match status:
        case Status.DRAFT:
            return Exits(frozenset({Exit.TICKET_REVIEW if change else Exit.COORDINATOR_MOVE}),
                         frees=False)
        case Status.NEW | Status.APPROVED | Status.REOPENED | Status.RELEASED:
            if change:
                return Exits(frozenset({Exit.TAKE}), frees=False)
            if kind is Kind.REFACTOR and title.endswith(MANY_IDEAS):
                return Exits(frozenset({Exit.MERGE}), frees=False)
            if kind is Kind.QUESTION and on_open_change:
                return Exits(frozenset({Exit.CHANGE_ANALYST}), frees=False)
            return Exits(frozenset({Exit.TICKET_ANALYST}), frees=False)
        case Status.ASSIGNED:
            return Exits(frozenset({Exit.HOLDER, Exit.RELEASE}), frees=False)
        case Status.BLOCKED:
            return Exits(frozenset({Exit.MERGE_LINE if change else Exit.COORDINATOR_LINE}),
                         frees=True)
        case Status.WAITING:
            return Exits(frozenset({Exit.CHANGE_CLOSE} if change
                                   else {Exit.COORDINATOR_LINE, Exit.CHANGE_CLOSE}), frees=True)
        case Status.DEFERRED:
            return Exits(frozenset({Exit.SWEEP}), frees=True)
        case Status.CLOSED:
            return Exits(frozenset() if change else frozenset({Exit.COORDINATOR_LINE}),
                         frees=False)
        case _:
            assert_never(status)


class Line(Protocol):
    @property
    def time(self) -> float: ...
    @property
    def status(self) -> Status: ...
    @property
    def agent(self) -> str: ...
    @property
    def note(self) -> str: ...


@dataclass(frozen=True)
class Freed:
    """The event that frees a ticket for a fresh ticket analyst, and the
    coordinator's line, where that event is one."""
    time: float
    line: Line | None


def freed[L: Line](log: tuple[L, ...], kind: Kind, filed: float) -> Freed:
    """The coordinator's line wins a tie with a move, as an analyst sent
    that line has seen the move as well."""
    last = next((ln for ln in reversed(log) if ln.agent == COORDINATOR), None)
    moved = max((ln.time for before, ln in zip(log, log[1:])
                 if ln.status is Status.REOPENED and frees(before.status, kind)), default=filed)
    if last is not None and last.time >= moved:
        return Freed(last.time, last)
    return Freed(moved, None)


def frees(status: Status, kind: Kind) -> bool:
    return exit_of(status, kind, on_open_change=False, title="").frees
