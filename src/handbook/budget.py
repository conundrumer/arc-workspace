"""A document's size budget: the most characters the text it bounds may
hold, given by the document's `budget` attribute, and the band below the
budget, from `BAND` of it, in which a size draws a warning. What each
command prints for a size within the band, past the budget, or for a
document with no budget is as `uv run python scripts/context.py --help`
gives it."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from handbook.paths import DOCUMENTS_ROOT, repo_label

BAND = 0.9
"""The share of a budget at which its band starts."""

BUDGET_ATTR = "budget"


class Standing(Enum):
    BELOW = "below"
    BAND = "band"
    PAST = "past"
    NONE = "none"


@dataclass(frozen=True)
class Size:
    """The size of the text a document bounds, against its budget."""

    doc: Path
    measured: Path
    """The file whose text the size measures: `doc`, or its rendering."""
    size: int
    budget: int | None

    @property
    def standing(self) -> Standing:
        if self.budget is None:
            return Standing.NONE
        if self.size > self.budget:
            return Standing.PAST
        if self.size >= BAND * self.budget:
            return Standing.BAND
        return Standing.BELOW

    def message(self) -> str | None:
        """What a command prints for this size, or None below the band."""
        fields = dict(path=repo_label(self.doc),
                      text=repo_label(self.measured), size=self.size,
                      budget=self.budget)
        match self.standing:
            case Standing.BELOW:
                return None
            case Standing.BAND:
                return WITHIN_BAND.format(**fields)
            case Standing.PAST:
                return PAST_BUDGET.format(**fields)
            case Standing.NONE:
                return NO_BUDGET.format(**fields)

    @property
    def fails(self) -> bool:
        return self.standing in (Standing.PAST, Standing.NONE)


WITHIN_BAND = mctx("Warning: {text} holds {size} characters, near the "
                   "budget of {budget} that {path} gives.")
PAST_BUDGET = mctx(
    "{text} holds {size} characters, past the budget of {budget} that {path} "
    "gives: cut that text, or raise the `+ budget:` line of {path} where "
    "[What a file holds](docs/handbook/editing.md#what-a-file-holds) keeps "
    "the text the raise admits.")
NO_BUDGET = mctx("{path} has no `+ budget:` line.")


def budget_of(doc: Path) -> int | None:
    """The budget `doc` gives, or None where it gives none. A value that is
    no whole number of characters is a fault."""
    value = nm.Registry(DOCUMENTS_ROOT).load(doc).attr(BUDGET_ATTR)
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        raise SystemExit(f"`{BUDGET_ATTR}: {value.strip()}` in "
                         f"{repo_label(doc)} is no number of characters") from None


def size(doc: Path, text: str, measured: Path | None = None) -> Size:
    """The size of `text`, which `doc` bounds, against `doc`'s budget:
    the text of `measured`, or of `doc` itself where `measured` is None."""
    return Size(doc, doc if measured is None else measured, len(text),
                budget_of(doc))


def report(sizes: list[Size]) -> None:
    """Print on stderr the warning of each size within its band, then, where
    any size fails, stop with the message of each that fails."""
    for found in sizes:
        if not found.fails and (message := found.message()) is not None:
            print(message, file=sys.stderr)
    if failing := [m for found in sizes
                   if found.fails and (m := found.message()) is not None]:
        raise SystemExit("\n".join(failing))


def checked(doc: Path, text: str, measured: Path) -> str:
    """`text`, the text of `measured` that `doc` bounds, once its size
    passes `report`."""
    report([size(doc, text, measured)])
    return text
