"""A document's size budget: the most characters the text it bounds may
hold, given by the document's `budget` attribute, and the band below the
budget, from `BAND` of it, in which a size draws a warning. What each
command prints for a size within the band, past the budget, or for a
document with no budget is as `uv run python scripts/context.py --help`
gives it, and the pass the merge files on a document past its budget as
`uv run python scripts/merge_change.py --help` gives it."""

from __future__ import annotations

import sys
from collections.abc import Callable
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
class WithoutLists:
    """A rendering's text without the lists its render computes
    (`handbook.listings`), which is not the text its file holds."""

    rendering: Path


@dataclass(frozen=True)
class WithoutAttributes:
    """A document's text without its attribute lines, which no render
    shows, and which is not the text its file holds."""

    doc: Path


type Measured = Path | WithoutLists | WithoutAttributes
"""What a size measures: the text of a file, `doc` or its rendering, a
rendering without its lists, or a document without its attribute lines."""


WITHOUT_LISTS = mctx("{path} without the lists its render computes")
WITHOUT_ATTRIBUTES = mctx("{path} without its attribute lines")


def measured_text(measured: Measured,
                  shown: Callable[[Path], str] = repo_label) -> str:
    """The words that name the text `measured` gives, with each path as
    `shown` gives it."""
    match measured:
        case WithoutLists(rendering=path):
            return WITHOUT_LISTS.format(path=shown(path))
        case WithoutAttributes(doc=path):
            return WITHOUT_ATTRIBUTES.format(path=shown(path))
        case Path():
            return shown(measured)


@dataclass(frozen=True)
class Size:
    """The size of the text a document bounds, against its budget."""

    doc: Path
    measured: Measured
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
                      text=measured_text(self.measured), size=self.size,
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
        return self.standing is Standing.NONE


WITHIN_BAND = mctx("Warning: {text} holds {size} characters, near the "
                   "budget of {budget} that {path} gives.")
# The sentence that tells the reader to cut no text and keep the `+ budget:`
# line comes from the user's words, session 7fd429fb-e3be-4173-9b0e-df52f507d6a2,
# 2026-10-16 (request 6-1476): "Hot fix budget rule so we do not enforce it
# until we have a proper resolution".
PAST_BUDGET = mctx(
    "Warning: {text} holds {size} characters, past the budget of {budget} "
    "that {path} gives. A merge files a whole-document pass on it where no "
    "such pass stands open. Outside that pass, cut no text for this, and "
    "leave the `+ budget:` line as it is.")
NO_BUDGET = mctx("{path} has no `+ budget:` line.")
NOT_A_NUMBER = mctx("`{attr}: {value}` in {doc} is no number of characters")


def budget_of(doc: Path) -> int | None:
    """The budget `doc` gives, or None where it gives none. A value that is
    no whole number of characters is a fault."""
    value = nm.Registry(DOCUMENTS_ROOT).load(doc).attr(BUDGET_ATTR)
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        raise SystemExit(NOT_A_NUMBER.format(attr=BUDGET_ATTR, value=value.strip(),
                                             doc=repo_label(doc))) from None


def size(doc: Path, text: str, measured: Measured | None = None) -> Size:
    """The size of `text`, which `doc` bounds, against `doc`'s budget:
    the text `measured` gives, or that of `doc` itself where `measured` is
    None."""
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
