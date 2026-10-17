"""One run of one lib component: a program that includes the lib and
instantiates the component, run through `souffle.SouffleEngine` with its
run cache.

An input `Position` value is the `(row, column)` of a cell, and its place
in the lib (`engine.program.cell_place`) is computed from the size of the
grid of the row's key. In a relation with no key column, a cell lies in the
one grid the call is given a size for. An output `Position` value crosses
as the first and third ints of its place, `(place[0], place[2])`, negative
ones included, in the frame the component's own declaration gives that
column, which need not be the grid of the row's key.

An `Offset` value crosses as its `(row, column)` displacement."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache

from cli.common import LIMITS
from engine.engine import ParseFailure, Tuples
from engine.program import (AdtValue, NilValue, RecordValue, RelationName, TypeName, Value, cell_place,
                            offset_place)
from handbook.lib import LIB_SRC
from souffle import SouffleEngine

INSTANCE = "c"
"""The name the component's instance takes in the program."""

type PyValue = int | float | str | tuple["PyValue", ...] | AdtValue | NilValue
type PyRow = tuple[PyValue, ...]
type Size = tuple[int, int]
"""A grid's height and width."""


class CallError(RuntimeError):
    """A component call the engine or the values given cannot run: the
    failure the engine returned, or the value that cannot cross."""


@dataclass(frozen=True)
class GridTypes:
    """The lib's types of a cell and of a translation."""

    position: StrEnum
    offset: StrEnum


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
    """The size of the grid of the cells of `row`, a row of the relation
    `name`, which has a `Position` column: the grid of the row's key, or,
    in a relation with no key column, the one grid `sizes` gives."""
    if sizes is None:
        raise CallError(f"`{name}` has a Position column and no sizes are given")
    if not columns.keyed:
        if len(sizes) != 1:
            raise CallError(f"`{name}` has a Position column and no key column, "
                            f"and the call gives sizes for {len(sizes)} grids, "
                            f"not one")
        return next(iter(sizes.values()))
    if row[0] not in sizes:
        raise CallError(f"no size is given for the key {row[0]!r} of `{name}`")
    return sizes[row[0]]


def _ints(v: PyValue, n: int) -> tuple[int, ...] | None:
    """`v` as a tuple of `n` ints; None where it is none."""
    if not (isinstance(v, tuple) and len(v) == n):
        return None
    ints = tuple(x for x in v if isinstance(x, int))
    return ints if len(ints) == n else None


def _row_in(name: str, columns: Columns, row: PyRow, grid: GridTypes,
            sizes: Mapping[PyValue, Size] | None) -> tuple[Value, ...]:
    out = [_value_in(v) for v in row]
    for i, t in enumerate(columns.types):
        if t == grid.position:
            h, w = _size(name, columns, row, sizes)
            cell = _ints(row[i], 2)
            if cell is None:
                raise CallError(f"`{name}` takes a cell as (row, column), "
                                f"not {row[i]!r}")
            out[i] = RecordValue(cell_place(cell[0], cell[1], h, w))
        elif t == grid.offset:
            move = _ints(row[i], 2)
            if move is None:
                raise CallError(f"`{name}` takes an offset as (row, column), "
                                f"not {row[i]!r}")
            out[i] = RecordValue(offset_place(move[0], move[1]))
    return tuple(out)


def _row_out(name: str, columns: Columns, row: Sequence[Value],
             grid: GridTypes) -> PyRow:
    out = [_value_out(v) for v in row]
    for i, t in enumerate(columns.types):
        if t == grid.position:
            place = _ints(out[i], 4)
            if place is None:
                raise CallError(f"`{name}` gives {out[i]!r}, which is no place")
            out[i] = (place[0], place[2])
        elif t == grid.offset:
            place = _ints(out[i], 4)
            if place is None or place != offset_place(place[0], place[2]):
                raise CallError(f"`{name}` gives {out[i]!r}, which is no "
                                f"translation")
            out[i] = (place[0], place[2])
    return tuple(out)


def call(component: str, type_args: Sequence[StrEnum], grid: GridTypes,
         columns: Mapping[str, Columns],
         inputs: Mapping[str, Iterable[PyRow] | None], outputs: Sequence[str],
         sizes: Mapping[PyValue, Size] | None) -> dict[str, Relation]:
    """The rows of each of the instance's relations `outputs`, after a run
    of `component` instantiated at `type_args` over the rows of each of its
    relations `inputs` that is not None. An input column whose type is
    `grid.position` is placed in the grid of its row's key (`_size`), an
    output one crosses as the first and third ints of its place, negative
    ones included, in the frame the component's declaration gives it, and
    a column whose type is `grid.offset` crosses as a displacement. Raises `CallError` where
    the program fails to parse, the run fails, or a value cannot cross."""
    engine = _engine()
    program = engine.lib_instance(LIB_SRC, INSTANCE, component,
                                  [TypeName((), t) for t in type_args])
    if isinstance(program, ParseFailure):
        raise CallError(program)
    facts = {RelationName((INSTANCE,), name):
             tuple(_row_in(name, columns[name], row, grid, sizes) for row in rows)
             for name, rows in inputs.items() if rows is not None}
    wanted = [RelationName((INSTANCE,), name) for name in outputs]
    result = engine.run(program, facts, wanted, LIMITS)
    if not isinstance(result, Tuples):
        raise CallError(result)
    return {rel.name: Relation(frozenset(
                _row_out(rel.name, columns[rel.name], row, grid)
                for row in result.relations[rel]))
            for rel in wanted}
