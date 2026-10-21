"""The values an entry document's render supplies: lists computed from
their source files, and `codex`, true for Codex instructions and false
for ordinary rendering. A render computes only the values it reads."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from functools import cache

import controlled_markdown as nm
from controlled_markdown import mctx
from engine import Program
from handbook.paths import repo_label
from solver.aggregate import proposers_path
from solver.readers import proposers, proposers_program
from souffle import SouffleEngine


class Listing(Enum):
    """The lists, by the variable that reads each: under `proposers`, one
    line per proposer of `programs/proposers.dl`, in the file's order, with
    the types of the value it proposes and the comment above it."""

    PROPOSERS = "proposers"


PROPOSER_LINE = mctx("- **{name}**({types}): {comment}.")

PROPOSERS_UNPARSED = mctx(
    "{path} does not parse with the lib, at line {line}: {message}. "
    "A render of a document that lists its proposers fails until it parses.")

NO_LISTING = mctx(
    "{path} reads unknown variable `{name}`; the supported variables are "
    "`codex` and {lists}.")


@cache
def _engine() -> SouffleEngine:
    """One engine for each render of a process, so `proposers_program`
    parses each text of the file once."""
    return SouffleEngine()


def _proposer_lines() -> str:
    """Where the file does not parse, the render fails, so that no
    rendering holds a stale or an empty list."""
    engine = _engine()
    program = proposers_program(engine)
    if not isinstance(program, Program):
        raise SystemExit(PROPOSERS_UNPARSED.format(
            path=repo_label(proposers_path()), line=program.line,
            message=program.message))
    return "\n".join(
        PROPOSER_LINE.format(name=p.name, types=", ".join(p.types),
                             comment=p.comment)
        for p in proposers(engine, program).values())


def _listing(name: str, document: nm.Node, registry: nm.Registry) -> Listing:
    try:
        return Listing(name)
    except ValueError:
        raise SystemExit(NO_LISTING.format(
            path=registry.rel(document), name=name,
            lists=", ".join(f"`{form.value}`" for form in Listing))) from None


def _listing_text(listing: Listing) -> str:
    match listing:
        case Listing.PROPOSERS:
            return _proposer_lines()


type Values = Callable[[nm.Node, nm.Registry], dict[str, str] | None]
"""The values an entry render gives the document it renders."""


def unlisted(_document: nm.Node, _registry: nm.Registry) -> None:
    """No values, so the render drops each block a list fills."""
    return None


def listings(document: nm.Node, registry: nm.Registry, *,
             codex: bool = False) -> dict[str, str] | None:
    """The value of each variable the entry document `document` reads; None
    where it reads none, so its render fills nothing."""
    names = nm.variables(document, registry)
    if not names:
        return None
    return {name: ("true" if codex else "") if name == "codex" else
            _listing_text(_listing(name, document, registry))
            for name in sorted(names)}
