"""The ticket vocabulary that the ticket tools under `scripts/` and the
operator's command (`operations`) share: the statuses a ticket moves
between, the status of a move into a take's queue (`queued`) and the last
line of a log that moves it into one, the
resolutions it closes with, the domains of its subject, its kinds, the
note of the line that files it and the route of a request, and the end
of the title of a `refactor` ticket on a module that holds more than one subject. What
takes a ticket out of each status, `exits` gives."""

import re
from collections.abc import Sequence
from enum import StrEnum
from typing import assert_never

class Status(StrEnum):
    """The directories under `tickets/` that a ticket's file moves between."""
    DRAFT = "draft"
    NEW = "new"
    """A ticket other than a `change`, filed, that no agent has taken since."""
    APPROVED = "approved"
    """A `change` whose ticket review passed and that no agent has taken
    since."""
    REOPENED = "reopened"
    """A ticket that a move from `blocked`, `waiting`, `deferred` or `closed`
    set back for a take."""
    RELEASED = "released"
    """A ticket whose hold ended without a settling move, by its holder or
    by the operator for a holder that is not live; it waits for its next
    take with what its holder left, a change's worktree included."""
    ASSIGNED = "assigned"
    BLOCKED = "blocked"
    """A ticket that waits on the user."""
    WAITING = "waiting"
    """A ticket that waits on a change."""
    CLOSED = "closed"
    DEFERRED = "deferred"
    """A ticket that waits on a condition `file_ticket.py` checks: a `delay`
    ticket on its group's summed loss, a `validation` ticket on its
    check."""


UNTAKEN = (Status.NEW, Status.APPROVED, Status.REOPENED, Status.RELEASED)
"""The statuses of a ticket that waits for a take, the statuses of a take's
queue, in the order of `Status`."""


SETTLED = (Status.CLOSED, Status.DEFERRED)
"""The statuses of a ticket that leaves its session's index out of the
indexes in which no agent runs that the main session's operators read."""


class Kind(StrEnum):
    """What a ticket is."""
    INTERFERENCE = "interference"
    DELAY = "delay"
    QUESTION = "question"
    BUG = "bug"
    PERFORMANCE = "performance"
    REFACTOR = "refactor"
    CHANGE = "change"
    REQUEST = "request"
    VALIDATION = "validation"
    """The check of a `request`'s need, which `file_ticket.py log` files
    as the request closes."""


def queued(source: Status | None, kind: Kind) -> Status:
    """The status of a move of a ticket of `kind` into a take's queue from
    `source`, None at its filing."""
    match source:
        case Status.BLOCKED | Status.WAITING | Status.DEFERRED | Status.CLOSED:
            return Status.REOPENED
        case Status.ASSIGNED:
            return Status.RELEASED
        case None | Status.DRAFT:
            return Status.APPROVED if kind is Kind.CHANGE else Status.NEW
        case Status.NEW | Status.APPROVED | Status.REOPENED | Status.RELEASED:
            raise ValueError(f"a ticket under `{source}` stands in a take's queue already")
        case _:
            assert_never(source)


class Resolution(StrEnum):
    """The words the note of a line into `closed` opens with."""
    FIXED = "fixed"
    DUPLICATE = "duplicate"
    CANNOT_REPRODUCE = "cannot-reproduce"
    WONTFIX = "wontfix"
    INVALID = "invalid"


class Verdict(StrEnum):
    """The words the notes of the lines the sweep (`file_ticket.py sweep`)
    writes on a `validation` ticket it moves out of `deferred` open with,
    after the resolution of a line into `closed`: what the check its
    `Validation` section gives shows."""
    VALIDATED = "validated"
    FAILED = "failed"
    UNEXERCISED = "unexercised"
    EXERCISED = "exercised"


class Domain(StrEnum):
    """What a ticket's subject is."""
    TASK = "task"
    CHANGE = "change"
    COMMIT = "commit"
    TICKET = "ticket"
    AGENT = "agent"


PASS_KINDS = frozenset({Kind.INTERFERENCE, Kind.DELAY})
EDITOR_KINDS = frozenset({Kind.QUESTION, Kind.BUG})
REVIEW_KINDS = frozenset({Kind.BUG, Kind.DELAY})


DEFECT_SECTIONS = ("Impact", "Evidence")
"""The sections of a ticket of each kind that has none of its own."""

COORDINATOR = "coordinator"
"""The `<agent>` of the coordinator's tickets and log lines."""

ALLOW = "allow"
"""The `<agent>` and the note of an allow line: a line, with no move, whose
id is the session id of the coordinator that wrote it, and which admits
the ticket past that session's `Op pause.` and `Op scope: own.`."""

class Wait(StrEnum):
    """What a ticket under `blocked` or `waiting` waits on, the word the
    note of the line into that status opens with."""
    USER = "user"
    CHANGE = "change"

    @property
    def status(self) -> Status:
        """The status of a ticket that waits on this."""
        match self:
            case Wait.USER:
                return Status.BLOCKED
            case Wait.CHANGE:
                return Status.WAITING


WAIT_STATUSES = frozenset(w.status for w in Wait)
"""The statuses of a ticket that waits, whose move in opens its note with a
wait."""


class Note(StrEnum):
    """The words the note of a log line opens with, which the procedures
    read it by."""
    FILED = "filed"
    """The note of the log line that files a ticket."""
    REVISED = "revised"
    """A ticket analyst revised the draft."""
    FINDING = "finding"
    SUGGESTION = "suggestion"
    LAST_REVISION = "last revision"
    """The draft opens with no further ticket review."""
    RERUN = "rerun"
    """The line gave the worktree of a run of the change that the command
    left after a conflict in the change's rebase. No step writes such a
    line now."""
    CONFLICT = "conflict"
    """The line gives the paths in which a merge call's rebase of the
    change onto `master` conflicts."""
    RECURS = "recurs"
    """`recurs <number>`: the `bug` `<number>` is a recurrence of the
    defect the ticket records, its root cause."""


class Route(StrEnum):
    """The routes of work that write a request, a brief or a span
    (`spans.py --help`)."""
    DIRECT = "direct"
    SEND = "op send"
    HOTFIX = "hotfix"
    FILE = "op file"
    DRAFT = "op draft"


ROUTE_NOTE = "route `{route}`"
"""The note, after `Note.FILED` on the line that files it, that gives the
route of a request."""

COUNT = re.compile(r"[1-9]\d*")
"""A session's index, the `<n>` of a ticket's number, or a bare number."""

TICKET_NUMBER = re.compile(rf"(?:(?P<session>{COUNT.pattern})-)?(?P<n>{COUNT.pattern})")
"""A ticket's number, `<session>-<n>`, or the bare number of a ticket filed
before a number gave the filing session's index."""

ROUTED = re.compile(rf"(?:{Note.FILED}: )?route `(?P<route>{'|'.join(Route)})`")
"""The opening of a note that gives a route (`ROUTE_NOTE`)."""

MANY_IDEAS = "many ideas in one place"
"""The end of the title of a `refactor` ticket on a module that holds more
than one subject."""


def note_opening(*alternatives: str) -> re.Pattern[str]:
    """The opening of a log note from the closed vocabulary `alternatives`."""
    return re.compile(rf"(?:{'|'.join(alternatives)})(?![\w-])")


def last_move_into(statuses: Sequence[Status], into: Status) -> int | None:
    """The index of the last of the statuses of a log's lines, in order,
    whose line moves the ticket into `into` from another status, the first
    line counting as such a move, or None where no line does."""
    moves = [i for i, s in enumerate(statuses)
             if s is into and (i == 0 or statuses[i - 1] is not into)]
    return moves[-1] if moves else None
