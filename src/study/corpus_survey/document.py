"""`docs/engine/corpus-survey.md` as the output of its sections: its head
lines, then each section of `SECTIONS` in order, each one the run computes
in place of the text the file holds under its heading."""

from collections.abc import Sequence
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from study.corpus_survey import (
    alts,
    determination,
    forms,
    join_orders,
    open_values,
    prefix,
    profiles,
    recursion,
    shapes,
    tasks,
)
from study.corpus_survey.section import Section

SURVEY = checkout.docs() / "engine" / "corpus-survey.md"

SECTIONS: tuple[Section, ...] = (
    forms.FORMS, alts.ALTS, forms.INSTANCES, recursion.RECURSION, forms.ARCDATA, forms.COLUMNS, forms.RARE,
    tasks.TASKS, shapes.BODIES, shapes.SYMMETRY, shapes.JOIN_SHAPES, prefix.PREFIX_SIZES, join_orders.JOIN_ORDERS,
    determination.DETERMINATION, open_values.OPEN_VALUES, open_values.MODELS, alts.FORMS_PER_SOLVER,
    profiles.RUNS, profiles.BOX_VALUES, profiles.IDENTS,
)
"""The sections in the order of the file."""

TITLE = "# Corpus survey"
HEAD = mctx("The output of `uv run python scripts/corpus_survey.py`, which rewrites the sections it is given, and with no name the sections that run no solver: change the script, never this file. Run a section only where a decision needs its numbers on the current corpus.")


def by_name(name: str) -> Section:
    """The section of that name; `KeyError` where none has it."""
    for s in SECTIONS:
        if s.name == name:
            return s
    raise KeyError(name)


def held(text: str) -> dict[str, str]:
    """The text the file holds under each section's heading, up to the next
    heading."""
    found: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if current is not None:
                found[current] = "\n".join(lines).strip("\n")
            current, lines = line.lstrip("#").strip(), []
        else:
            lines.append(line)
    if current is not None:
        found[current] = "\n".join(lines).strip("\n")
    return found


def rewrite(chosen: Sequence[Section], path: Path = SURVEY) -> None:
    """Rewrites the file at `path` with each section of `chosen` computed,
    and each other section as the file holds it."""
    kept = held(path.read_text()) if path.exists() else {}
    computed = {s.heading: s.compute() for s in chosen}
    parts = [TITLE, HEAD]
    for s in SECTIONS:
        text = computed.get(s.heading, kept.get(s.heading, ""))
        parts.append(f"{'#' * s.level} {s.heading}\n\n{text}".rstrip("\n"))
    path.write_text("\n\n".join(parts) + "\n")
