"""The ticket vocabulary that the ticket tools under `scripts/` and the
operator's command (`operations`) share: the statuses a ticket moves
between, the resolutions it closes with, the domains of its subject, its
kinds, the note of the line that files it, and the end of the title of a
`refactor` ticket on a module that holds more than one subject. What
takes a ticket out of each status, `exits` gives."""

import re
from enum import StrEnum

class Status(StrEnum):
    """The directories under `tickets/` that a ticket's file moves between."""
    DRAFT = "draft"
    OPEN = "open"
    ASSIGNED = "assigned"
    BLOCKED = "blocked"
    CLOSED = "closed"
    DEFERRED = "deferred"
    """A ticket that waits on a condition `file_ticket.py` checks: a `delay`
    ticket on its group's summed loss, a `request` on its `Validation`
    check."""


SETTLED = (Status.CLOSED, Status.DEFERRED)
"""The statuses of a ticket that leaves its session's index out of the
indexes in which no agent runs that the main session's operators read."""


class Resolution(StrEnum):
    """The words the note of a line into `closed` opens with."""
    FIXED = "fixed"
    DUPLICATE = "duplicate"
    CANNOT_REPRODUCE = "cannot-reproduce"
    WONTFIX = "wontfix"
    INVALID = "invalid"


class Verdict(StrEnum):
    """The words the notes of the lines the sweep (`file_ticket.py sweep`)
    writes on a `request` it moves out of `deferred` open with, after the
    resolution of a line into `closed`: what the check its `Validation`
    section gives shows."""
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


PASS_KINDS = frozenset({Kind.INTERFERENCE, Kind.DELAY})
EDITOR_KINDS = frozenset({Kind.QUESTION, Kind.BUG})
REVIEW_KINDS = frozenset({Kind.BUG, Kind.PERFORMANCE})


DEFECT_SECTIONS = ("Impact", "Evidence")
"""The sections of a ticket of each kind that has none of its own."""

COORDINATOR = "coordinator"
"""The `<agent>` of the coordinator's tickets and log lines."""

class Wait(StrEnum):
    """What a ticket under `blocked` waits on, the word the note of the line
    into `blocked` opens with."""
    USER = "user"
    CHANGE = "change"


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
    """The line gives the worktree of a run of the change that the command
    left, which `worktrees.logged_worktree` passes over."""

MANY_IDEAS = "many ideas in one place"
"""The end of the title of a `refactor` ticket on a module that holds more
than one subject."""


def note_opening(*alternatives: str) -> re.Pattern[str]:
    """The opening of a log note from the closed vocabulary `alternatives`."""
    return re.compile(rf"(?:{'|'.join(alternatives)})(?![\w-])")
