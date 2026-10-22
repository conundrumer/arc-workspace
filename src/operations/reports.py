"""The fixed forms of the replies of the agents the operator launches that
the command reads, each written in the document of the agent that writes
it, and the reads of them. A reply in no such form is read as the form's
absence: a review that does not pass and no module split."""

import re
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

from operations.roles import Role
from operations.state import Agent
from operations.worktrees import fingerprint

DONE = "done"
"""The opening, in any case, of the report of a `handbook-expanded` agent
where every item is done."""

NO_FINDING = "no finding stands"
"""The opening, in any case, of a doc reviewer's reply where no finding
stands and none is held back."""

AT_CAP = "at the round cap"
"""The opening, in any case, of a doc reviewer's reply at the last round
its brief gives, over the findings that hold the change, and of the reason
an editor's report gives for each finding of the last round of a review
an item has it make that it leaves for a decision."""

WORKTREE = "Worktree:"
"""The opening of the line that ends a doc reviewer's or an item
checker's reply, before the `worktrees.fingerprint` of the change's
worktree it read."""

TICKETS_FILED = "## Tickets filed"
"""The heading of a solver pass's report over the numbers of the tickets
the pass filed."""

CONCEPT_FAULTS = "## Concept faults"
"""The heading of a solver pass's report over the concept faults the pass
gives, one list item each, or `none`."""

SPLIT_OPENING = r"^\s*[-*]\s+split:"
SPLIT = re.compile(SPLIT_OPENING + r" `(?P<path>[^`]+)`(?:; left unsplit: (?P<part>.+))?$",
                   re.MULTILINE)
"""An item of a code editor's report that gives a module it split, by the
path a `refactor` ticket cites, with the part it left unsplit, where one
is."""
SPLIT_ITEM = re.compile(SPLIT_OPENING + r".*$", re.MULTILINE)
"""An item of a code editor's report that opens as a `SPLIT` item does,
in any form."""

FOR_COORDINATOR = "## For the coordinator"
"""The heading at the end of a ticket analyst's reply, over the part of it
for the coordinator: the decisions it brings the user, the changes it
tells the user, and the items it leaves unfinished."""
TO_EDITOR = "## To {role}"
"""The heading in a ticket analyst's reply, before `FOR_COORDINATOR`, over
the findings it keeps and the edits it decides for the editor of the role
`Role.value` fills in; the command delivers that section to that editor
(`to_editor`)."""
LEFT_FOR_DECISION = "## Left for a decision"
"""The heading at the end of an item checker's reply, over the findings
and the items the editors' reports leave for a decision and the `refactor`
places they give as standing."""


def heading_part(text: str, heading: str) -> str | None:
    """The text after the last line of `text` that is `heading` alone, or
    None where no line is."""
    last = None
    for last in re.finditer(rf"^{re.escape(heading)}[ \t]*$", text, re.MULTILINE):
        pass
    return None if last is None else text[last.end():]


def section(text: str, heading: str) -> str | None:
    """The text under the last line of `text` that is `heading` alone, up
    to the next `## ` heading, or None where no line is `heading`."""
    body = heading_part(text, heading)
    return None if body is None else body.split("\n## ", 1)[0]


def to_editor(a: Agent, role: Role) -> str | None:
    """The text of the section under `TO_EDITOR` for `role` in the last
    report of the analyst `a`, up to the next `## ` heading, or None where
    `a` has no report or no such section, or the section holds only
    whitespace or `none`."""
    r = a.last_report
    body = None if r is None else section(r.text, TO_EDITOR.format(role=role.value))
    text = (body or "").strip()
    return None if not text or NONE_ITEM.match(text) else text


def section_items(text: str, heading: str) -> tuple[str, ...]:
    """The top-level list items of the section of `text` under `heading`
    (`section`), each with the lines nested under it, less an item that is
    `none`; none where `text` has no such section."""
    items: list[list[str]] = []
    for line in (section(text, heading) or "").splitlines():
        if TOP_ITEM.match(line):
            items.append([line])
        elif items and line.strip() and indent(line) > 0:
            items[-1].append(line)
    return tuple(t for item in items if (t := "\n".join(item).strip()).lower().strip(
        "-*+ .") != "none")


def worktree_line(ln: str) -> bool:
    return ln.strip().startswith(WORKTREE)


def left_for_decision(a: Agent) -> str | None:
    """What an item checker's latest reply leaves for a decision, or None
    where that reply holds nothing back. The reply holds nothing back only
    where it has a line `LEFT_FOR_DECISION` alone and the text after the
    last such line, less each `worktree_line` and each blank line, is the
    one line `none`, with or without a list marker, a closing `.` and
    capitals. For each other reply the result is the text after that line,
    or, where the reply has no such line, the whole reply, in each case
    less each `worktree_line`."""
    r = a.last_report
    if a.role is not Role.ITEM_CHECKER or r is None:
        return None
    part = heading_part(r.text, LEFT_FOR_DECISION)
    kept = [ln for ln in (r.text if part is None else part).splitlines()
            if not worktree_line(ln)]
    lines = [ln.strip() for ln in kept if ln.strip()]
    if part is not None and len(lines) == 1 and NONE_ITEM.match(lines[0]):
        return None
    return "\n".join(kept).strip("\n")


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

TOP_ITEM = re.compile(rf"^{LIST_MARKER}[ \t]+")
"""The opening of a list item at the top level of a section."""

NONE_ITEM = re.compile(rf"(?:{LIST_MARKER}[ \t]+)?none[ \t]*\.?$", re.IGNORECASE)
"""The one line of a part that holds nothing back."""

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


def done(a: Agent) -> bool:
    return opens(a, DONE)


def no_finding(a: Agent) -> bool:
    return opens(a, NO_FINDING)


def at_cap(a: Agent) -> bool:
    return opens(a, AT_CAP)


def reviewed_state(a: Agent) -> str | None:
    r = a.last_report
    if r is None:
        return None
    lines = [ln.strip() for ln in r.text.splitlines() if worktree_line(ln)]
    return lines[-1].removeprefix(WORKTREE).strip() or None if lines else None


def shows_current(a: Agent, w: Path) -> bool:
    seen = reviewed_state(a)
    return seen is not None and seen == fingerprint(w)


def editor_report(a: Agent) -> str:
    """The text of a code editor's latest report, or none where `a` is no
    code editor or has no report."""
    r = a.last_report
    return "" if a.role is not Role.CODE_EDITOR or r is None else r.text


def splits(a: Agent) -> dict[str, str | None]:
    """The modules a code editor's latest report gives as split, each with
    the part it left unsplit, or None where it left none."""
    return {m["path"]: m["part"] for m in SPLIT.finditer(editor_report(a))}


def unread_split(a: Agent) -> bool:
    """Whether a code editor's latest report holds a `SPLIT_ITEM` that
    `SPLIT` does not read."""
    return any(SPLIT.fullmatch(m[0]) is None for m in SPLIT_ITEM.finditer(editor_report(a)))


def coordinator_part(a: Agent) -> tuple[list[tuple[Label, list[str]]], list[str]]:
    """The part of a ticket analyst's latest reply under `FOR_COORDINATOR`:
    its `LABELED` items, each by its label with its lines and the lines
    nested under it, and the other lines, or none where it has no such
    part."""
    r = a.last_report
    part = None if r is None else heading_part(r.text, FOR_COORDINATOR)
    if a.role is not Role.TICKET_ANALYST or part is None:
        return [], []
    labeled: list[tuple[Label, list[str]]] = []
    other: list[str] = []
    top: int | None = None
    for line in part.splitlines():
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
