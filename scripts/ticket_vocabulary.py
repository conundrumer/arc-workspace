"""The ticket vocabulary: the statuses a ticket moves between, the
resolutions it closes with, the domains of its subject, its kinds, and the
kinds each filing agent may file."""

from collections.abc import Iterable
from enum import StrEnum

from controlled_markdown import mctx
from transcripts import Refused


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


PASS_KINDS = frozenset({Kind.INTERFERENCE, Kind.DELAY})
EDITOR_KINDS = frozenset({Kind.QUESTION, Kind.BUG})
REVIEW_KINDS = frozenset({Kind.BUG, Kind.PERFORMANCE})


class Filer(StrEnum):
    """A filing agent, by its name."""
    ANALYZE = "analyze"
    CREATE = "create"
    REFINE = "refine"
    TRANSCRIPT_REVIEW = "transcript-review"
    SUPERVISOR_CHECK = "supervisor-check"
    HANDBOOK = "handbook"
    HANDBOOK_EXPANDED = "handbook-expanded"
    CODE_EDITOR = "code-editor"
    DOC_EDITOR = "doc-editor"
    OPERATOR = "operator"
    DOC_REVIEWER = "doc-reviewer"
    TICKET_REVIEWER = "ticket-reviewer"
    CODE_REVIEWER = "code-reviewer"
    COORDINATOR = "coordinator"
    TICKET_ANALYST = "ticket-analyst"


FILER_KINDS: dict[Filer, frozenset[Kind]] = {
    Filer.ANALYZE: PASS_KINDS,
    Filer.CREATE: PASS_KINDS,
    Filer.REFINE: PASS_KINDS,
    Filer.TRANSCRIPT_REVIEW: PASS_KINDS,
    Filer.SUPERVISOR_CHECK: PASS_KINDS,
    Filer.HANDBOOK: PASS_KINDS,
    Filer.HANDBOOK_EXPANDED: PASS_KINDS,
    Filer.CODE_EDITOR: EDITOR_KINDS,
    Filer.DOC_EDITOR: EDITOR_KINDS,
    Filer.OPERATOR: REVIEW_KINDS,
    Filer.DOC_REVIEWER: REVIEW_KINDS,
    Filer.TICKET_REVIEWER: REVIEW_KINDS,
    Filer.CODE_REVIEWER: REVIEW_KINDS | {Kind.REFACTOR, Kind.QUESTION},
    Filer.COORDINATOR: frozenset({Kind.CHANGE, Kind.BUG}),
    Filer.TICKET_ANALYST: frozenset({Kind.CHANGE}),
}
"""The kinds each filing agent, by its name, may file."""


def ticked(names: Iterable[str]) -> str:
    return ", ".join(f"`{n}`" for n in names)


def is_agent(agent: str, name: str) -> bool:
    return agent == name or agent.startswith(f"{name}-")


def filer_kinds(agent: str) -> frozenset[Kind]:
    """The kinds `agent` may file: those of its name, or of the longest
    name it extends with `-<suffix>`. Any other name is refused."""
    for name in sorted(Filer, key=len, reverse=True):
        if is_agent(agent, name):
            return FILER_KINDS[name]
    raise Refused(mctx("the document of `{agent}` gives it no ticket kinds: the agents that file are {names}").format(
        agent=agent, names=ticked(Filer)))
