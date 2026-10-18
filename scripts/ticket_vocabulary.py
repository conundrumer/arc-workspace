"""The kinds each filing agent may file. The rest of the ticket vocabulary
is `ticketing.vocabulary`."""

from collections.abc import Iterable
from enum import StrEnum

from controlled_markdown import mctx
from operations.roles import Role
from ticketing.vocabulary import COORDINATOR, EDITOR_KINDS, PASS_KINDS, REVIEW_KINDS, Kind
from transcript_snapshots import Refused


class Filer(StrEnum):
    """A filer by its name: an agent, or a script that files a ticket."""
    ANALYZE = Role.ANALYZE.value
    CREATE = Role.CREATE.value
    REFINE = Role.REFINE.value
    TRANSCRIPT_REVIEW = Role.TRANSCRIPT_REVIEW.value
    HANDBOOK = "handbook"
    HANDBOOK_EXPANDED = Role.HANDBOOK_EXPANDED.value
    CODE_EDITOR = Role.CODE_EDITOR.value
    DOC_EDITOR = Role.DOC_EDITOR.value
    OPERATOR = Role.OPERATOR.value
    DOC_REVIEWER = Role.DOC_REVIEWER.value
    DESIGN_REVIEWER = Role.DESIGN_REVIEWER.value
    TICKET_REVIEWER = Role.TICKET_REVIEWER.value
    CODE_REVIEWER = Role.CODE_REVIEWER.value
    LIB_REVIEWER = Role.LIB_REVIEWER.value
    COORDINATOR = COORDINATOR
    TICKET_ANALYST = Role.TICKET_ANALYST.value
    MERGE_CHANGE = "merge-change"
    """`scripts/merge_change.py`, which files a whole-document pass
    (`document_pass.py`)."""


CODE_REVIEW_KINDS = REVIEW_KINDS | {Kind.REFACTOR, Kind.QUESTION}
"""The kinds a reviewer of code merged to `master` files."""

FILER_KINDS: dict[Filer, frozenset[Kind]] = {
    Filer.ANALYZE: PASS_KINDS,
    Filer.CREATE: PASS_KINDS,
    Filer.REFINE: PASS_KINDS,
    Filer.TRANSCRIPT_REVIEW: PASS_KINDS,
    Filer.HANDBOOK: frozenset({Kind.BUG, Kind.DELAY}),
    Filer.HANDBOOK_EXPANDED: frozenset({Kind.BUG, Kind.DELAY}),
    Filer.CODE_EDITOR: EDITOR_KINDS,
    Filer.DOC_EDITOR: EDITOR_KINDS,
    Filer.OPERATOR: REVIEW_KINDS | {Kind.DELAY},
    Filer.DOC_REVIEWER: REVIEW_KINDS,
    Filer.DESIGN_REVIEWER: REVIEW_KINDS | {Kind.QUESTION},
    Filer.TICKET_REVIEWER: REVIEW_KINDS,
    Filer.CODE_REVIEWER: CODE_REVIEW_KINDS,
    Filer.LIB_REVIEWER: CODE_REVIEW_KINDS,
    Filer.COORDINATOR: frozenset({Kind.REQUEST, Kind.BUG}),
    Filer.TICKET_ANALYST: frozenset({Kind.CHANGE, Kind.BUG}),
    Filer.MERGE_CHANGE: frozenset({Kind.CHANGE}),
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
    raise Refused(mctx("the document of `{agent}` gives it no ticket kinds: the filers, by their names, are {names}").format(
        agent=agent, names=ticked(Filer)))
