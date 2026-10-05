"""The spec of a card: one question the user decides on, drawn as one HTML page.

    uv run python scripts/cards.py render <spec>.json

That prints the path it wrote.
"""

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

type LineRange = tuple[int, int]


@dataclass
class CodeSlice:
    """A run of lines from one file, shown with some of them highlighted."""

    # Why the slice is shown, in a few words.
    label: str
    # The file, relative to the repo root, or absolute.
    path: str
    # A 1-based inclusive [start, end] line range.
    lines: LineRange
    # 1-based line numbers inside that range.
    highlight: list[int] = field(default_factory=list[int])


@dataclass
class Table:
    """A small table of text cells shown under the witness grids."""

    title: str
    headers: list[str]
    rows: list[list[str]]


@dataclass
class Card:
    # Names the file written to work/cards/<name>.html, and heads the page.
    name: str
    # A free label shown under the title. A card of a family shares its kind.
    kind: str
    # The task, whose train pairs and test pairs are drawn.
    task_id: str
    # As one sentence, stated so that the options are the only answers to it.
    question: str = ""
    codes: list[CodeSlice] = field(default_factory=list[CodeSlice])
    # Paths to grid text files, in the format `arc.task.read_grid` reads.
    # With none, the task's first train input is the witness, which suits a
    # question the task's own pairs already separate. Write a witness file
    # when the question turns on an input the task does not contain.
    witnesses: list[str] = field(default_factory=list[str])
    # The user answers by index, so the options carry the whole decision:
    # each states a position rather than a direction, they exclude each
    # other, and together they cover the answers. The expected answer goes
    # first.
    options: list[str] = field(default_factory=list[str])
    tables: list[Table] = field(default_factory=list[Table])
    # The `.dl` file to run on each witness, defaulting to the task's own.
    solver: str | None = None
    # The cases the shipped solver lacks, each by its name as the tool prints
    # it (`solver.names.name`): `$Free`, `$Free & $Wide`, `concept`. Naming
    # them filters the witnesses: a witness is kept only when a dropped
    # case's grid differs from every kept case's. With no witness left, the
    # card falls back to the task's first train input, under a note.
    dropped: list[str] = field(default_factory=list[str])
    # A recorded reason, quoted above the witness.
    quote: str = ""
    # Where that quote sits, as `<path>:<line>`.
    quote_source: str = ""
    # Keeps every witness listed, so `dropped` filters none of them.
    all_witnesses: bool = False


def card_from_dict(data: dict) -> Card:
    """A Card from its JSON form. An unknown key is an error, since a card
    that silently drops one states less than it was asked to."""
    known = {f.name for f in fields(Card)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(
            f"unknown card fields: {', '.join(unknown)}. "
            f"a card states: {', '.join(f.name for f in fields(Card))}"
        )
    values = dict(data)
    codes = [
        CodeSlice(
            label=c["label"],
            path=c["path"],
            lines=(c["lines"][0], c["lines"][1]),
            highlight=list(c.get("highlight", [])),
        )
        for c in values.pop("codes", [])
    ]
    tables = [
        Table(title=t["title"], headers=list(t["headers"]),
              rows=[list(r) for r in t["rows"]])
        for t in values.pop("tables", [])
    ]
    return Card(codes=codes, tables=tables, **values)


def load_card(path: str | Path) -> Card:
    return card_from_dict(json.loads(Path(path).read_text()))
