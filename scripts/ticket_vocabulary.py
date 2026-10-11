"""The kinds each filing agent may file. The rest of the ticket vocabulary
is `ticketing.vocabulary`."""

from collections.abc import Iterable
from enum import StrEnum

from controlled_markdown import mctx
from ticketing.vocabulary import COORDINATOR, EDITOR_KINDS, PASS_KINDS, REVIEW_KINDS, Kind
from transcripts import Refused


class Filer(StrEnum):
    """A filing agent, by its name."""
    ANALYZE = "analyze"
    CREATE = "create"
    REFINE = "refine"
    TRANSCRIPT_REVIEW = "transcript-review"
    HANDBOOK = "handbook"
    HANDBOOK_EXPANDED = "handbook-expanded"
    CODE_EDITOR = "code-editor"
    DOC_EDITOR = "doc-editor"
    OPERATOR = "operator"
    DOC_REVIEWER = "doc-reviewer"
    TICKET_REVIEWER = "ticket-reviewer"
    CODE_REVIEWER = "code-reviewer"
    COORDINATOR = COORDINATOR
    TICKET_ANALYST = "ticket-analyst"


FILER_KINDS: dict[Filer, frozenset[Kind]] = {
    Filer.ANALYZE: PASS_KINDS,
    Filer.CREATE: PASS_KINDS,
    Filer.REFINE: PASS_KINDS,
    Filer.TRANSCRIPT_REVIEW: PASS_KINDS,
    Filer.HANDBOOK: frozenset({Kind.BUG, Kind.DELAY}),
    Filer.HANDBOOK_EXPANDED: frozenset({Kind.BUG, Kind.DELAY}),
    Filer.CODE_EDITOR: EDITOR_KINDS,
    Filer.DOC_EDITOR: EDITOR_KINDS,
    Filer.OPERATOR: REVIEW_KINDS,
    Filer.DOC_REVIEWER: REVIEW_KINDS,
    Filer.TICKET_REVIEWER: REVIEW_KINDS,
    Filer.CODE_REVIEWER: REVIEW_KINDS | {Kind.REFACTOR, Kind.QUESTION},
    Filer.COORDINATOR: frozenset({Kind.REQUEST, Kind.BUG}),
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
