"""The spec of a card: one question the user decides on, drawn as one HTML
page the Artifact tool publishes as it stands.

    uv run python scripts/cards.py render <spec>.json

That prints the path it wrote.
"""

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

from engine import checkout

type LineRange = tuple[int, int]
type Captions = dict[str, dict[str, str]]

OPTION_FORM = 'an option is its text or {"text": ..., "cases": [...]}'


def from_root(path: str) -> Path:
    """A path a card spec gives: from the repository root, or absolute."""
    return checkout.ROOT / path


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
class Option:
    """One answer the user may give, with the cases whose grids stand for it
    where the options are competing readings."""

    text: str
    # Each by its name as `Card.dropped` gives it, and only those whose
    # grids stand for this option. A case may stand for several options,
    # and a case the run gives may stand for none. The page labels each
    # case's grid with the number of each option that names it. The render
    # fails on a name the run on a witness does not give. Naming them
    # filters no witness. A card names them or gives `dropped`, not both.
    cases: list[str] = field(default_factory=list[str])


@dataclass
class Card:
    # One file name: it names the file written to work/cards/<name>.html,
    # heads the page, and is the page's title, which the Artifact tool
    # shows as its name.
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
    # first. In JSON, `OPTION_FORM` gives an option's forms.
    options: list[Option] = field(default_factory=list[Option])
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
    # A sentence under a case's grid on a witness: what the grid shows, or
    # that the grid on this witness says nothing about the question. Keyed
    # by the witness label, then the case name, as the page prints them;
    # the fallback witness by the label the page gives it. Where the case
    # gives several grids, it stands under each; where it gives an error,
    # under the error text. The render fails on a case the run on that
    # witness does not give, and on a witness the page does not draw. A
    # card with `dropped` and no `all_witnesses` cannot know which of its
    # listed witnesses, or the fallback in their place, the page draws, so
    # there a caption on one of those passes undrawn.
    captions: Captions = field(default_factory=dict[str, dict[str, str]])


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
    captions = {
        witness: dict(cases)
        for witness, cases in values.pop("captions", {}).items()
    }
    options = [_option(o) for o in values.pop("options", [])]
    card = Card(codes=codes, tables=tables, captions=captions,
                options=options, **values)
    _check_option_cases(card)
    return card


def _option(entry: object) -> Option:
    """An Option from its JSON form. Any form but the two `OPTION_FORM`
    gives is an error: a bare string as `cases` would read as one case per
    character."""
    if isinstance(entry, str):
        return Option(entry)
    if not isinstance(entry, dict) or set(entry) - {"text", "cases"}:
        raise ValueError(f"{OPTION_FORM}, not {entry!r}")
    text, cases = entry.get("text"), entry.get("cases", [])
    if not isinstance(text, str) or not isinstance(cases, list) \
            or not all(isinstance(c, str) for c in cases):
        raise ValueError(f"{OPTION_FORM}, not {entry!r}")
    return Option(text, list(cases))


def options_of(card: Card, case: str) -> list[int]:
    return [number for number, option in enumerate(card.options, 1)
            if case in option.cases]


def options_phrase(numbers: list[int]) -> str:
    listed = ", ".join(map(str, numbers))
    return f"options {listed}" if len(numbers) > 1 else f"option {listed}"


def _check_option_cases(card: Card) -> None:
    if card.dropped and any(o.cases for o in card.options):
        raise ValueError("a card gives `dropped` or the cases of its "
                         "options, not both")


def load_card(path: str | Path) -> Card:
    return card_from_dict(json.loads(Path(path).read_text()))
