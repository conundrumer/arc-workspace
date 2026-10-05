"""One run of one lib component: a program that includes the lib and
instantiates the component, run through `souffle.SouffleEngine` with its
run cache.

A `Position` value crosses as the `(row, column)` of its cell, and its
place in the lib (`engine.program.cell_place`) is computed from the size of
the grid of the row's key."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache

from cli.common import LIMITS
from engine.engine import ParseFailure, Tuples
from engine.program import AdtValue, RecordValue, RelationName, Value, cell_place
from handbook.context import LIB_SRC
from souffle import SouffleEngine

INSTANCE = "c"
"""The name the component's instance takes in the program."""

type PyValue = int | float | str | tuple["PyValue", ...] | AdtValue
type PyRow = tuple[PyValue, ...]
type Size = tuple[int, int]
"""A grid's height and width."""


class CallError(RuntimeError):
    """A component call the engine or the values given cannot run: the
    failure the engine returned, or the value that cannot cross."""


@dataclass(frozen=True)
class Columns:
    """A relation of the instance: its column types, after the type
    arguments, and whether its first column is the component's key."""

    types: tuple[StrEnum, ...]
    keyed: bool


@dataclass(frozen=True)
class Relation:
    """An output relation's rows."""

    rows: frozenset[PyRow]

    def map(self) -> dict[PyValue, PyValue]:
        """The last column by the columns before it, one column standing
        alone. Raises `CallError` where two rows agree on every column but
        the last."""
        return _map(self.rows)

    def map_per_key(self) -> dict[PyValue, dict[PyValue, PyValue]]:
        """For each key, `map` of its rows less the key."""
        out: dict[PyValue, set[PyRow]] = {}
        for row in self.rows:
            out.setdefault(row[0], set()).add(row[1:])
        return {k: _map(rows) for k, rows in out.items()}


def _map(rows: Iterable[PyRow]) -> dict[PyValue, PyValue]:
    out: dict[PyValue, PyValue] = {}
    for row in rows:
        k = row[0] if len(row) == 2 else row[:-1]
        if k in out and out[k] != row[-1]:
            raise CallError(f"two values for {k!r}: {out[k]!r} and {row[-1]!r}")
        out[k] = row[-1]
    return out


@cache
def _engine() -> SouffleEngine:
    return SouffleEngine()


def _value_in(v: PyValue) -> Value:
    return RecordValue(tuple(_value_in(f) for f in v)) if isinstance(v, tuple) else v


def _value_out(v: Value) -> PyValue:
    return tuple(_value_out(f) for f in v.fields) if isinstance(v, RecordValue) else v


def _size(name: str, columns: Columns, row: PyRow,
          sizes: Mapping[PyValue, Size] | None) -> Size:
    """The size of the grid of `row`'s key, for a relation with a
    `Position` column."""
    if not columns.keyed:
        raise CallError(f"`{name}` has a Position column and no key column")
    if sizes is None:
        raise CallError(f"`{name}` has a Position column and no sizes are given")
    if row[0] not in sizes:
        raise CallError(f"no size is given for the key {row[0]!r} of `{name}`")
    return sizes[row[0]]


def _ints(v: PyValue, n: int) -> tuple[int, ...] | None:
    """`v` as a tuple of `n` ints; None where it is none."""
    if not (isinstance(v, tuple) and len(v) == n):
        return None
    ints = tuple(x for x in v if isinstance(x, int))
    return ints if len(ints) == n else None


def _row_in(name: str, columns: Columns, row: PyRow, position: StrEnum,
            sizes: Mapping[PyValue, Size] | None) -> tuple[Value, ...]:
    out = [_value_in(v) for v in row]
    for i, t in enumerate(columns.types):
        if t == position:
            h, w = _size(name, columns, row, sizes)
            cell = _ints(row[i], 2)
            if cell is None:
                raise CallError(f"`{name}` takes a cell as (row, column), "
                                f"not {row[i]!r}")
            out[i] = RecordValue(cell_place(cell[0], cell[1], h, w))
    return tuple(out)


def _row_out(name: str, columns: Columns, row: Sequence[Value], position: StrEnum,
             sizes: Mapping[PyValue, Size] | None) -> PyRow:
    out = [_value_out(v) for v in row]
    for i, t in enumerate(columns.types):
        if t == position:
            h, w = _size(name, columns, tuple(out), sizes)
            place = _ints(out[i], 4)
            if place is None or place != cell_place(place[0], place[2], h, w):
                raise CallError(f"`{name}` gives {out[i]!r}, which is no cell of a "
                                f"{h}x{w} grid")
            out[i] = (place[0], place[2])
    return tuple(out)


def call(component: str, type_args: Sequence[StrEnum], position: StrEnum,
         columns: Mapping[str, Columns],
         inputs: Mapping[str, Iterable[PyRow] | None], outputs: Sequence[str],
         sizes: Mapping[PyValue, Size] | None) -> dict[str, Relation]:
    """The rows of each of the instance's relations `outputs`, after a run
    of `component` instantiated at `type_args` over the rows of each of its
    relations `inputs` that is not None. A column whose type is `position`
    crosses as a cell of the grid `sizes` gives for the row's key. Raises
    `CallError` where the program fails to parse, the run fails, or a value
    cannot cross."""
    engine = _engine()
    args = ", ".join(type_args)
    text = (f'#include "{LIB_SRC.name}"\n'
            f".init {INSTANCE} = {component}<{args}>\n")
    program = engine.parse(text, LIB_SRC.parent)
    if isinstance(program, ParseFailure):
        raise CallError(program)
    facts = {RelationName((INSTANCE,), name):
             tuple(_row_in(name, columns[name], row, position, sizes) for row in rows)
             for name, rows in inputs.items() if rows is not None}
    wanted = [RelationName((INSTANCE,), name) for name in outputs]
    result = engine.run(program, facts, wanted, LIMITS)
    if not isinstance(result, Tuples):
        raise CallError(result)
    return {rel.name: Relation(frozenset(
                _row_out(rel.name, columns[rel.name], row, position, sizes)
                for row in result.relations[rel]))
            for rel in wanted}
