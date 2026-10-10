"""The fixed forms of the replies of the agents the operator launches that
the command reads, each written in the document of the agent that writes
it, and the reads of them. A reply in no such form is read as the form's
absence: a review that does not pass and no module split."""

import re
from collections.abc import Iterable
from enum import StrEnum

from operations.roles import Role
from operations.state import Agent

BUDGET_PASSED = "budget passed"
"""The opening, in any case, of the reply of a code editor that ended its
turn at its budget with work left."""

NO_FINDING = "no finding stands"
"""The opening, in any case, of a doc reviewer's reply where no finding
stands and none is held back."""

TICKETS_FILED = "## Tickets filed"
"""The heading of a solver pass's report over the numbers of the tickets
the pass filed."""

SPLIT = re.compile(r"^\s*[-*]\s+split: `(?P<path>[^`]+)`(?:; left unsplit: (?P<part>.+))?$",
                   re.MULTILINE)
"""An item of a code editor's report that gives a module it split, by the
path a `refactor` ticket cites, with the part it left unsplit, where one
is."""

FOR_COORDINATOR = "## For the coordinator"
"""The heading at the end of a ticket analyst's reply, over the part of it
for the coordinator: the decisions it brings the user, the changes it
tells the user, and the items it leaves unfinished."""
LEFT_FOR_DECISION = "## Left for a decision"
"""The heading at the end of an item checker's reply, over the findings
and the items the editors' reports leave for a decision and the `refactor`
places they give as standing."""


def left_for_decision(a: Agent) -> str | None:
    """The part of an item checker's latest reply under
    `LEFT_FOR_DECISION`, or None where it has no such part or that part is
    empty."""
    r = a.last_report
    if a.role is not Role.ITEM_CHECKER or r is None or LEFT_FOR_DECISION not in r.text:
        return None
    return r.text.rsplit(LEFT_FOR_DECISION, 1)[1].strip("\n") or None


class Label(StrEnum):
    """The labels of the kinds of item of the part for the coordinator."""
    DECISION = "decision"
    TELL = "tell"
    UNFINISHED = "unfinished"


OPEN_LABELS = (Label.DECISION, Label.UNFINISHED)
"""The labels of the items of that part that leave the change's work open
for the coordinator."""

LABELS = f"(?P<label>{'|'.join(Label)})"

LIST_MARKER = r"(?:[-*+]|\d+[.)])"
"""The marker of a Markdown list item, which the command reads past at the
opening of a line."""

LABEL_OPENING = rf"^(?P<indent>[ \t]*)(?:{LIST_MARKER}[ \t]+)?[*_`]*{LABELS}"
"""The opening of an item of the part for the coordinator by one of
`LABELS`, in any case, after any list marker or none, and inside any
emphasis or code markup."""

LABELED = re.compile(LABEL_OPENING + r"[*_`]*[ \t]*:", re.IGNORECASE)
"""An item of the part for the coordinator, opened by the label of its
kind and a colon, inside or outside the markup."""

MISLABELED = re.compile(LABEL_OPENING + r"\b", re.IGNORECASE)
"""An item of that part that opens with a label with no colon after it,
which `LABELED` does not read."""


def opens(a: Agent, opening: str) -> bool:
    r = a.last_report
    return r is not None and r.text.lstrip().lower().startswith(opening)


def budget_passed(a: Agent) -> bool:
    return opens(a, BUDGET_PASSED)


def no_finding(a: Agent) -> bool:
    return opens(a, NO_FINDING)



def splits(a: Agent) -> dict[str, str | None]:
    """The modules a code editor's latest report gives as split, each with
    the part it left unsplit, or None where it left none."""
    r = a.last_report
    if a.role is not Role.CODE_EDITOR or r is None:
        return {}
    return {m["path"]: m["part"] for m in SPLIT.finditer(r.text)}


def coordinator_part(a: Agent) -> tuple[list[tuple[Label, list[str]]], list[str]]:
    """The part of a ticket analyst's latest reply under `FOR_COORDINATOR`:
    its `LABELED` items, each by its label with its lines and the lines
    nested under it, and the other lines, or none where it has no such
    part."""
    r = a.last_report
    if a.role is not Role.TICKET_ANALYST or r is None or FOR_COORDINATOR not in r.text:
        return [], []
    labeled: list[tuple[Label, list[str]]] = []
    other: list[str] = []
    top: int | None = None
    for line in r.text.rsplit(FOR_COORDINATOR, 1)[1].splitlines():
        if top is not None and (not line.strip() or indent(line) > top):
            labeled[-1][1].append(line)
            continue
        m = LABELED.match(line)
        top = len(m["indent"]) if m else None
        if m:
            labeled.append((Label(m["label"].lower()), [line]))
        else:
            other.append(line)
    return labeled, other


def indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def items_of(a: Agent, labels: Iterable[Label]) -> str | None:
    """The `LABELED` items of the part of a ticket analyst's latest reply
    for the coordinator labeled by one of `labels`, each with the lines
    nested under it, or None where that part holds no such item."""
    wanted = set(labels)
    return "\n".join(ln for label, lines in coordinator_part(a)[0] if label in wanted
                     for ln in lines).strip("\n") or None


def mislabeled(a: Agent) -> list[str]:
    """The `MISLABELED` items of the part of a ticket analyst's latest
    reply for the coordinator, outside its `LABELED` items."""
    return [ln.strip() for ln in coordinator_part(a)[1] if MISLABELED.match(ln)]
