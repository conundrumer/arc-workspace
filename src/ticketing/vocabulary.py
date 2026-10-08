"""The ticket vocabulary that the ticket tools under `scripts/` and the
operator's command (`operating`) share: the statuses a ticket moves
between, the resolutions it closes with, the domains of its subject, its
kinds, the note of the line that files it, and the end of the title of a
`refactor` ticket on a module that holds more than one subject."""

from enum import StrEnum

class Status(StrEnum):
    """The directories under `tickets/` that a ticket's file moves between."""
    DRAFT = "draft"
    OPEN = "open"
    ASSIGNED = "assigned"
    BLOCKED = "blocked"
    CLOSED = "closed"


class Resolution(StrEnum):
    """The words the note of a line into `closed` opens with."""
    FIXED = "fixed"
    DUPLICATE = "duplicate"
    CANNOT_REPRODUCE = "cannot-reproduce"
    WONTFIX = "wontfix"
    INVALID = "invalid"


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


FILED = "filed"
"""The note of the log line that files a ticket."""

MANY_IDEAS = "many ideas in one place"
"""The end of the title of a `refactor` ticket on a module that holds more
than one subject."""
