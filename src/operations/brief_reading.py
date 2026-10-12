"""The reading of a brief's or a message's text back: the number of items
a brief that gives several items of the same work gives, and the budgets
a text states."""

import re
from string import Formatter

from operations.briefs import ITEM_LINES, ITEM_SEPARATOR
from operations.reports import LIST_MARKER

ITEM = r"[^\s,]+"


def item_pattern(template: str) -> re.Pattern[str]:
    """The lines `template` renders, with the item list in the group
    `numbers`."""
    parts = []
    for literal, slot, _, _ in Formatter().parse(template):
        parts.append(re.escape(literal))
        if slot == "numbers":
            parts.append(rf"(?P<numbers>{ITEM}(?:{ITEM_SEPARATOR}{ITEM})*)")
        elif slot is not None:
            parts.append(".*?")
    return re.compile("".join(parts))


ITEM_PATTERNS = tuple(item_pattern(t) for t in ITEM_LINES)


def items(brief: str) -> int | None:
    """The number of items a brief gives, where its first line is one of
    `ITEM_LINES`, or None where it is none of them."""
    first = brief.split("\n", 1)[0]
    for pattern in ITEM_PATTERNS:
        if (m := pattern.fullmatch(first)) is not None:
            return len(m["numbers"].split(ITEM_SEPARATOR))
    return None


BUDGET_LINE = re.compile(r"Budget: (?P<minutes>\d+(?:\.\d+)?) minutes(?:[.,;:].*)?")
"""A line that states a budget, past its list marker, in the form
`profile_runs.py --help` gives, which `BUDGET` renders."""

MARKED_OPENING = re.compile(rf"^\s*{LIST_MARKER}?\s*")


def unmarked(line: str) -> str:
    return MARKED_OPENING.sub("", line).strip()


def budgets(text: str) -> set[float]:
    """The minutes each `BUDGET_LINE` of `text` states."""
    return {float(m["minutes"]) for line in text.splitlines()
            if (m := BUDGET_LINE.fullmatch(unmarked(line))) is not None}

