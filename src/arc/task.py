"""Task data model — minimal in-memory representation — and the JSON form
of a pair, which `load` and the runner's pairs file read (`read_pair`) and
`arc.materialize` writes (`pair_json`)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, get_args

from arc.patch import SetT
from controlled_markdown import mctx

TASK_ID = r"[0-9a-f]{8}"
"""The form of a task id."""

type Grid = list[list[int]]
type AltKind = Literal["rule", "tiebreak"]

ALT_KINDS: tuple[AltKind, ...] = get_args(AltKind.__value__)

type PairSection = SetT | Literal["pair"]
"""A section pairs stand under: a task's train or test pairs
(`PAIR_SECTIONS`), or the one section of a pairs file that holds a bare
list of pairs (`LIST_SECTION`)."""

PAIR_SECTIONS: tuple[SetT, ...] = get_args(SetT.__value__)
LIST_SECTION: Literal["pair"] = "pair"

# The keys of a pair's JSON form, in the order `pair_json` writes them.
# `INDEX` holds the pair's index in its section, which a reader takes
# unread; `PAIR_KEYS` are the keys it reads, and `ALT_KEYS` the keys of
# its alt.
INDEX = "index"
INPUT, OUTPUT, ALT = "input", "output", "alt"
PAIR_KEYS = (INPUT, OUTPUT, ALT)
KIND, GRID = "kind", "grid"
ALT_KEYS = (KIND, GRID)

COLORS = range(10)
"""The colors a cell of a grid holds, 0 to 9."""
TASKS_DIR = Path(__file__).resolve().parents[2] / "data" / "tasks"


@dataclass
class Alt:
    kind: AltKind
    grid: Grid


@dataclass
class Example:
    input: Grid
    output: Grid
    # ARC scoring is pass@2, so at most one alternative valid output per example.
    alt: Alt | None = None


@dataclass(frozen=True)
class Probe:
    """A pair without an output: its run prints the grids the solver emits
    in place of a comparison."""

    input: Grid


@dataclass
class Task:
    train: list[Example] = field(default_factory=list[Example])
    test: list[Example] = field(default_factory=list[Example])


class PairFormError(ValueError):
    """A pair's JSON off its form (`read_pair`)."""


def pair_name(section: PairSection, index: int) -> str:
    """A pair by its section and its index there, as every command writes
    it: `train 0`, `test 1`."""
    return f"{section} {index}"


def spelled(keys: tuple[str, ...]) -> str:
    """`keys` as a message lists them, in order: each in code, the last
    after `and`."""
    shown = [f"`{k}`" for k in keys]
    return " and ".join([", ".join(shown[:-1]), shown[-1]] if len(shown) > 1
                        else shown)


def as_grid(value: object) -> Grid:
    """`value` as a grid: a nonempty list of rows of one nonzero width,
    each cell a color from 0 to 9. Raises ValueError, saying what is off,
    where it is none."""
    if not isinstance(value, list) or not all(isinstance(row, list)
                                              for row in value):
        raise ValueError(mctx("not a list of rows"))
    if not value or not value[0]:
        raise ValueError(mctx("empty grid"))
    widths = {len(row) for row in value}
    if len(widths) != 1:
        raise ValueError(mctx("rows differ in width: {widths}").format(
            widths=sorted(widths)))
    for row in value:
        for cell in row:
            if isinstance(cell, bool) or not isinstance(cell, int) \
                    or cell not in COLORS:
                raise ValueError(mctx("cell out of range: {cell}").format(
                    cell=repr(cell)))
    return value


class GridFormError(ValueError):
    """A written grid that writes no grid (`read_grid`)."""


def read_grid(written: str) -> Grid:
    """The grid the text writes: one line per row, one digit per cell,
    spaces and commas between cells optional, blank lines and `#` lines
    skipped, and text that starts with `[` read as JSON. Raises
    `GridFormError`, saying what is off, where it writes none."""
    stripped = written.strip()
    try:
        if stripped.startswith("["):
            rows = json.loads(stripped)
        else:
            rows = [[int(ch) for ch in re.sub(r"[\s,]", "", line)]
                    for line in stripped.splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
        return as_grid(rows)
    except (ValueError, TypeError) as e:
        raise GridFormError(e) from None


def _grid(where: str, key: str, value: object) -> Grid:
    """The grid a pair holds under `key`, in the pair `where` gives (`as_grid`).
    Raises `PairFormError` where it holds none."""
    try:
        return as_grid(value)
    except ValueError as e:
        raise PairFormError(mctx("{where}: `{key}` is no grid: {fault}").format(
            where=where, key=key, fault=e)) from None


def _alt_kind(where: str, value: object) -> AltKind:
    """The alt kind `value` spells, in the pair `where` gives. Raises
    `PairFormError` where it spells none."""
    for kind in ALT_KINDS:
        if kind == value:
            return kind
    raise PairFormError(mctx(
        "{where}: `{kind}` is no alt kind; see "
        "[Alt outputs](docs/handbook/solver-file.md#alt-outputs)").format(
            where=where, kind=value))


def read_pair(section: PairSection, index: int, data: object) -> Example | Probe:
    """The pair at `index` of `section`, from its JSON form: an `Example`,
    or a `Probe` where it holds no output. Raises `PairFormError` where the
    pair holds a key outside `PAIR_KEYS` and `INDEX`, holds no input, holds
    an alt and no output, holds an alt that is not an object of `ALT_KEYS`
    whose kind is an `AltKind`
    ([Alt outputs](docs/handbook/solver-file.md#alt-outputs)), or holds an
    input, an output or an alt grid that is no grid (`as_grid`)."""
    where = pair_name(section, index)
    if not isinstance(data, dict):
        raise PairFormError(mctx("{where} is no JSON object").format(
            where=where))
    for key in data:
        if key not in PAIR_KEYS and key != INDEX:
            raise PairFormError(mctx(
                "{where}: `{key}` is no key of a pair; a pair holds {keys}")
                .format(where=where, key=key, keys=spelled(PAIR_KEYS)))
    if INPUT not in data:
        raise PairFormError(mctx("{where} holds no `input`").format(
            where=where))
    grid_in = _grid(where, INPUT, data[INPUT])
    if data.get(OUTPUT) is None:
        if ALT in data:
            raise PairFormError(mctx(
                "{where} holds an `alt` and no `output`").format(where=where))
        return Probe(grid_in)
    output = _grid(where, OUTPUT, data[OUTPUT])
    if ALT not in data:
        return Example(input=grid_in, output=output)
    alt = data[ALT]
    if not isinstance(alt, dict) or set(alt) != set(ALT_KEYS):
        raise PairFormError(mctx(
            "{where}: the `alt` is not an object of {keys}").format(
                where=where, keys=spelled(ALT_KEYS)))
    return Example(input=grid_in, output=output,
                   alt=Alt(kind=_alt_kind(where, alt[KIND]),
                           grid=_grid(where, f"{ALT}.{GRID}", alt[GRID])))


def pair_json(ex: Example, index: int) -> dict[str, Any]:
    """`ex` in its JSON form (`read_pair`), with `index`, its index in its
    section."""
    d: dict[str, Any] = {INDEX: index, INPUT: ex.input, OUTPUT: ex.output}
    if ex.alt is not None:
        d[ALT] = {KIND: ex.alt.kind, GRID: ex.alt.grid}
    return d


def _examples(path: Path, section: SetT, pairs: list[object]) -> list[Example]:
    """The pairs of `section` of the task file at `path` (`read_pair`).
    Raises `PairFormError` where a pair is off its form or holds no
    output."""
    examples: list[Example] = []
    for i, data in enumerate(pairs):
        try:
            pair = read_pair(section, i, data)
        except PairFormError as e:
            raise PairFormError(f"{path}: {e}") from None
        if isinstance(pair, Probe):
            raise PairFormError(mctx("{path}: {where} holds no `output`")
                                .format(path=path,
                                        where=pair_name(section, i)))
        examples.append(pair)
    return examples


def task_file(task_id: str) -> Path:
    """Where the materialized task `task_id` stands."""
    return TASKS_DIR / f"{task_id}.json"


def load(task_id: str) -> Task:
    """Load a materialized task from data/tasks/. Patches applied; upstream errors fixed."""
    path = task_file(task_id)
    if not path.exists():
        raise FileNotFoundError(f"no materialized task at {path}")
    data = json.loads(path.read_text())
    return Task(**{section: _examples(path, section, data[section])
                   for section in PAIR_SECTIONS})
