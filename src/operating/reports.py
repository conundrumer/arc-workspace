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


def for_coordinator(a: Agent) -> str | None:
    """The part of a ticket analyst's latest reply under `FOR_COORDINATOR`,
    or None where it has none or that part is empty."""
    r = a.last_report
    if a.role is not Role.TICKET_ANALYST or r is None or FOR_COORDINATOR not in r.text:
        return None
    part = r.text.rsplit(FOR_COORDINATOR, 1)[1].strip()
    return part or None
