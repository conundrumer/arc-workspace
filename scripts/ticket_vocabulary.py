"""The kinds each filing agent may file, and the check that each agent's
own documents have it file only those. The rest of the ticket vocabulary
is `ticketing.vocabulary`."""

import re
from collections.abc import Iterable, Iterator
from enum import StrEnum
from pathlib import Path

from controlled_markdown import mctx
from handbook.agents import agent_names, agent_renderings, next_file, next_readers, next_text
from handbook.checklist import Checklist, PartCall, checklist_agents, walk
from handbook.paths import repo_label
from operations.roles import DECISION_ANALYST, DRAFT_ANALYST, Role
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
    ITEM_CHECKER = Role.ITEM_CHECKER.value
    COORDINATOR = COORDINATOR
    TICKET_ANALYST = Role.TICKET_ANALYST.value
    DECISION_ANALYST = DECISION_ANALYST
    DRAFT_ANALYST = DRAFT_ANALYST
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
    Filer.DECISION_ANALYST: frozenset({Kind.CHANGE, Kind.BUG, Kind.REFACTOR}),
    Filer.DRAFT_ANALYST: frozenset({Kind.CHANGE, Kind.BUG}),
    Filer.MERGE_CHANGE: frozenset({Kind.CHANGE}),
    Filer.ITEM_CHECKER: frozenset({Kind.BUG}),
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


_KIND = "`(" + "|".join(k.value for k in Kind) + ")`"
NOUN_BEFORE = ("a", "an", "the", "each", "every", "that", "this", "its", "your", "their", "one",
               "report", "ticket", "part", "own")
"""The words before `file` that make it a noun."""
_FILE = "".join(rf"(?<!\b{w} )" for w in NOUN_BEFORE) + r"\bfile\b"
FILING = re.compile("|".join([
    rf"{_FILE}\s+(?:[\w-]+\s+){{0,3}}?{_KIND}",
    rf"{_FILE}\s+(?:[\w-]+\s+){{0,3}}?as\s+a\s+ticket\s+of\s+kind\s+{_KIND}",
    rf"{_KIND}(?:\s+ticket)?\s+you\s+file\b",
]), re.IGNORECASE)
"""A filing clause: the bare verb `file`, on a ticket whose kind it gives
in backticks before or after the verb. A sentence on a ticket another agent
`filed` holds none."""

KIND_LIST = re.compile(r"\bticket you file\b[^`]*?\b(?:is|kind)\b(.*)", re.IGNORECASE)
"""A filing clause that gives the kinds of the ticket as a list, each kind
in backticks after it, as in "The kind of a ticket you file is `question`
..., or `bug`"."""

SENTENCE_END = re.compile(r"(?<=[.;])\s+(?=[A-Z`\[])")


def filed_kinds(text: str) -> Iterator[tuple[int, Kind]]:
    """Each kind a filing clause of `text` gives, with the number of its
    line."""
    for n, line in enumerate(text.splitlines(), 1):
        for sentence in SENTENCE_END.split(line):
            kinds = [next(g for g in m.groups() if g) for m in FILING.finditer(sentence)]
            if (listed := KIND_LIST.search(sentence)) is not None:
                kinds += re.findall(_KIND, listed.group(1))
            for kind in dict.fromkeys(kinds):
                yield n, Kind(kind.lower())


def _files(agent: str, kind: Kind) -> bool:
    try:
        return kind in filer_kinds(agent)
    except Refused:
        return False


def document_findings(agent: str, path: Path, text: str) -> list[str]:
    """A finding for each filing clause of `text`, a document of `agent` at
    `path`, whose kind `filer_kinds(agent)` lacks or whose agent it
    refuses."""
    out: list[str] = []
    for n, kind in filed_kinds(text):
        if not _files(agent, kind):
            out.append(UNFILED.format(where=f"{repo_label(path)}:{n}", agent=agent, kind=kind.value))
    return out


UNFILED = mctx("{where}: the document has `{agent}` file a `{kind}` ticket, and `FILER_KINDS` in `scripts/ticket_vocabulary.py` gives `{agent}` no `{kind}`")


def filing_findings() -> list[str]:
    """The findings of `document_findings` over each agent's own documents:
    its rendered prompt, its `-next` document where it has one, and each
    part file its checklist gives."""
    texts = [(agent, r.path, r.text) for agent, r in zip(agent_names(), agent_renderings(), strict=True)]
    texts += [(agent, next_file(agent), next_text(agent)) for agent in next_readers()]
    for agent in checklist_agents():
        parts = dict.fromkeys(i.file for i in walk(Checklist(agent).items) if isinstance(i, PartCall))
        texts += [(agent, f, f.read_text()) for f in parts]
    return [finding for agent, path, text in texts for finding in document_findings(agent, path, text)]
