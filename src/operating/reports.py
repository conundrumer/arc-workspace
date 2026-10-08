"""The fixed forms of the replies of the agents the operator launches that
the command reads, each written in the document of the agent that writes
it, and the reads of them. A reply in no such form is read as the form's
absence: an editor not finished, a review with findings, no place standing
and no module split."""

import re

from operating.roles import Role
from operating.state import Agent

DONE = ("done", "blocked")
"""The opening, in any case, of the report of an editor that leaves nothing
for a decision."""

NO_FINDING = "no finding stands"
"""The opening, in any case, of a doc reviewer's reply where no finding
stands and none is held back."""

REVIEW = "## Review"
STANDS = re.compile(r"^\s*[-*]\s+stands:", re.MULTILINE)
"""An item of a code editor's `Review` section that gives a place as
standing."""

SPLIT = re.compile(r"^\s*[-*]\s+split: `(?P<path>[^`]+)`(?:; left unsplit: (?P<part>.+))?$",
                   re.MULTILINE)
"""An item of a code editor's report that gives a module it split, by the
path a `refactor` ticket cites, with the part it left unsplit, where one
is."""

FINDING = re.compile(r"^\s*[-*]\s+`(?P<path>[^`]+)`:", re.MULTILINE)
"""A finding of a doc reviewer's reply, opened by the path of the file it
falls on."""

HELD_BACK = re.compile(r"^#+\s*Held back\s*$", re.MULTILINE)

FOR_COORDINATOR = "## For the coordinator"
"""The heading at the end of a ticket analyst's reply, over the part of it
for the coordinator: the decisions it brings the user, the changes it
tells the user, and the items it leaves unfinished."""

LABELS = "(?:decision|tell|unfinished)"
"""The labels of the kinds of item of the part for the coordinator."""

LABEL_OPENING = rf"^(?P<indent>[ \t]*)(?:(?:[-*+]|\d+[.)])[ \t]+)?[*_`]*{LABELS}"
"""The opening of an item of the part for the coordinator by one of
`LABELS`, in any case, after any list marker or none, and inside any
emphasis or code markup."""

LABELED = re.compile(LABEL_OPENING + r"[*_`]*[ \t]*:", re.IGNORECASE)
"""An item of the part for the coordinator, opened by the label of its
kind and a colon, inside or outside the markup."""

MISLABELED = re.compile(LABEL_OPENING + r"\b", re.IGNORECASE)
"""An item of that part that opens with a label with no colon after it,
which `LABELED` does not read."""

HAND_OVER = "hand-over:"
"""The opening of the reply of an agent that ends with its open work for a
fresh agent, as the message on an outgrown alert asks."""


def opens(a: Agent, opening: str | tuple[str, ...]) -> bool:
    r = a.last_report
    return r is not None and r.text.lstrip().lower().startswith(opening)


def finished(a: Agent) -> bool:
    return opens(a, DONE)


def no_finding(a: Agent) -> bool:
    return opens(a, NO_FINDING)


def handed_over(a: Agent) -> bool:
    return opens(a, HAND_OVER)


def standing(a: Agent) -> bool:
    """Whether the `Review` section of a code editor's latest report gives
    a place as standing."""
    r = a.last_report
    if a.role is not Role.CODE_EDITOR or r is None or REVIEW not in r.text:
        return False
    return STANDS.search(r.text.split(REVIEW, 1)[1]) is not None


def splits(a: Agent) -> dict[str, str | None]:
    """The modules a code editor's latest report gives as split, each with
    the part it left unsplit, or None where it left none."""
    r = a.last_report
    if a.role is not Role.CODE_EDITOR or r is None:
        return {}
    return {m["path"]: m["part"] for m in SPLIT.finditer(r.text)}


def finding_paths(a: Agent) -> list[str]:
    """The paths of the files the findings of a doc reviewer's latest reply
    fall on, other than those under its `Held back` heading."""
    r = a.last_report
    if r is None:
        return []
    body = HELD_BACK.split(r.text, 1)[0]
    return list(dict.fromkeys(m["path"] for m in FINDING.finditer(body)))


def coordinator_part(a: Agent) -> tuple[list[str], list[str]]:
    """The lines of the part of a ticket analyst's latest reply under
    `FOR_COORDINATOR`, as the lines of its `LABELED` items, each with the
    lines nested under it, and the other lines, or none where it has no
    such part."""
    r = a.last_report
    if a.role is not Role.TICKET_ANALYST or r is None or FOR_COORDINATOR not in r.text:
        return [], []
    labeled: list[str] = []
    other: list[str] = []
    top: int | None = None
    for line in r.text.rsplit(FOR_COORDINATOR, 1)[1].splitlines():
        if top is not None and (not line.strip() or indent(line) > top):
            labeled.append(line)
            continue
        m = LABELED.match(line)
        top = len(m["indent"]) if m else None
        (labeled if m else other).append(line)
    return labeled, other


def indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def for_coordinator(a: Agent) -> str | None:
    """The `LABELED` items of the part of a ticket analyst's latest reply
    for the coordinator, each with the lines nested under it, or None where
    that part holds no such item."""
    return "\n".join(coordinator_part(a)[0]).strip("\n") or None


def mislabeled(a: Agent) -> list[str]:
    """The `MISLABELED` items of the part of a ticket analyst's latest
    reply for the coordinator, outside its `LABELED` items."""
    return [ln.strip() for ln in coordinator_part(a)[1] if MISLABELED.match(ln)]
