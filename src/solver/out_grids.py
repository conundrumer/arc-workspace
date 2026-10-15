"""The grids `out`'s rows hold: the columns of `out`, the cell and the
grid size a `Position` value gives, and the grids a case's rows give, or
why they give none."""

from collections.abc import Callable, Iterable, Sequence
from itertools import product
from dataclasses import dataclass
from enum import StrEnum

from engine import (
    Grid,
    NilValue,
    Program,
    RecordValue,
    Row,
    Rows,
    Value,
)
from engine.program import (
    RelationDecl,
    own,
)
from engine.quotes import quotes
from solver.aggregate import (
    TOP,
)
from solver.model import (
    Case,
)
from solver.outcome import Grids
from solver.witness import Resolution
from solver.value_order import value_key
from solver.vocabulary import (
    CHOICE,
    DEMONSTRATED_CHOICE,
    OPEN_VALUE,
    OUTPUT,
    TIEBREAK_RESOLUTION,
)
from solver.undefined import (
    Cell,
    ConflictingCells,
    InconsistentBounds,
    MissingCells,
    NegativeEdges,
    NoOutput,
    Undefined,
    UndefinedReason,
)


def out_decl(program: Program) -> RelationDecl | None:
    """`out`'s declaration in the solver's own text at the top level; None
    where it declares none."""
    return next((r for r in program.relations if r.name == OUTPUT.name
                 and r.scope == TOP and own(r.span)), None)


class ResolutionType(StrEnum):
    """The types of the columns of `out` that split a case's rows into
    grids (solver-file.md, under "Cases")."""

    DEMONSTRATED = DEMONSTRATED_CHOICE
    TIEBREAK = TIEBREAK_RESOLUTION


@dataclass(frozen=True)
class ResolutionColumn:
    """A column of `out` that splits a case's rows into grids."""

    index: int
    type: ResolutionType


@dataclass(frozen=True)
class OutColumns:
    """The case column, the resolution columns and the open-value column of
    `out`, by type (solver-file.md, under "Cases" and "Alt outputs"); None
    where `out` has none. The resolution columns stand in `out`'s column
    order, and a resolution value holds one value per column, in that
    order."""

    case: int | None
    resolution: tuple[ResolutionColumn, ...]
    open: int | None


def out_columns(program: Program) -> OutColumns:
    """`out`'s columns (`OutColumns`)."""
    decl = out_decl(program)
    if decl is None:
        return OutColumns(None, (), None)
    types = [c.type.text for c in decl.columns]

    def at(name: str) -> int | None:
        return types.index(name) if name in types else None

    resolving = tuple(ResolutionColumn(i, ResolutionType(t))
                      for i, t in enumerate(types)
                      if t in ResolutionType)
    return OutColumns(at(CHOICE), resolving, at(OPEN_VALUE))


@dataclass(frozen=True)
class Margins:
    """A `Position` value (lib.dl: `.type Position = Box`, `[t, b, l, r]`):
    a cell's distances to the top, bottom, left and right edges of its
    grid."""

    top: int
    bottom: int
    left: int
    right: int

    @property
    def cell(self) -> Cell:
        """The cell's row and column."""
        return self.top, self.left

    @property
    def size(self) -> Cell:
        """The height and width of the grid the cell stands in."""
        return self.top + self.bottom + 1, self.left + self.right + 1


def position(value: object) -> Margins | None:
    """The margins a `Position` value holds; None where `value` is no
    record of four numbers."""
    if not isinstance(value, RecordValue) or len(value.fields) != 4:
        return None
    t, b, l, r = value.fields
    if type(t) is not int or type(b) is not int or type(l) is not int \
            or type(r) is not int:
        return None
    return Margins(t, b, l, r)


type Place = tuple[Cell, Cell, tuple[int, int, int, int] | None]
"""What `_grid_of` reads of a position value: the cell, the size of its
grid, and its margins where one of them is negative."""

_UNSEEN = object()


def _place(value: object) -> Place | None:
    m = position(value)
    if m is None:
        return None
    edges = (m.top, m.bottom, m.left, m.right)
    return m.cell, m.size, edges if min(edges) < 0 else None


def _grid_of(cells: Sequence[Row], places: dict[int, Place | None]
             ) -> Grid | UndefinedReason:
    """The total grid the cells give, or why they give none: a cell with a
    negative distance to an edge, two frame sizes, a cell with two colors,
    or a cell of the frame with none.
    `places` holds what is read of each position value already read, by
    the value's identity, as the rows of one run share their values."""
    at: dict[Cell, int] = {}
    two: set[Cell] = set()
    sizes: dict[Cell, None] = {}
    negative: dict[tuple[int, int, int, int], None] = {}
    for row in cells:
        color = row[1]
        key = id(row[0])
        p = places.get(key, _UNSEEN)
        if p is _UNSEEN:
            p = places[key] = _place(row[0])
        if p is None or type(color) is not int:
            raise ValueError(f"`out` holds a row with no cell: {row}")
        cell, size, below = p  # type: ignore[misc]
        if below is not None:
            negative[below] = None
            continue
        sizes[size] = None
        first = at.setdefault(cell, color)
        if first != color:
            two.add(cell)
    if negative:
        return NegativeEdges(tuple(negative))
    if len(sizes) != 1:
        return InconsistentBounds(tuple(sizes))
    if two:
        return ConflictingCells(tuple(sorted(two)))
    (height, width), = sizes
    missing = tuple((i, j) for i in range(height) for j in range(width)
                    if (i, j) not in at)
    if missing:
        return MissingCells(missing)
    return tuple(tuple(at[(i, j)] for j in range(width))
                 for i in range(height))


def rows_by_base(rows: Rows, case_col: int | None) -> dict[Value, list[Row]]:
    """`out`'s rows by the base in their case column, each list in the
    rows' order; empty where `out` has no case column."""
    return {} if case_col is None else by_value(rows, case_col)


def by_values(rows: Sequence[Row], cols: Sequence[int]
              ) -> dict[Resolution, list[Row]]:
    """`rows` by their values in columns `cols`, as `by_value` groups
    them at each column in turn."""
    if not cols:
        return {(): list(rows)}
    return {(v, *rest): group
            for v, mine in by_value(rows, cols[0]).items()
            for rest, group in by_values(mine, cols[1:]).items()}


def by_value(rows: Sequence[Row], col: int) -> dict[Value, list[Row]]:
    """`rows` by their value in column `col`, each list in the rows' order,
    the values in the order they first stand. The rows of one run share one
    object per distinct value, so the rows are grouped by object first and
    each object is hashed once; where two objects are equal, by value."""
    by_id: dict[int, list[Row]] = {}
    for r in rows:
        group = by_id.get(id(r[col]))
        if group is None:
            group = by_id[id(r[col])] = []
        group.append(r)
    out = {group[0][col]: group for group in by_id.values()}
    if len(out) == len(by_id):
        return out
    out = {}
    for r in rows:
        out.setdefault(r[col], []).append(r)
    return out


type FieldValues = tuple[tuple[Value, ...], ...]
"""A case's values at each field of `OpenValue` on a run, in field order:
the values of the field's `@open` relation on the run
(`solver.open_values.open_fields`)."""


def case_grids(columns: OutColumns, mine: Sequence[Row],
               margins: dict[int, Place | None],
               fields: FieldValues) -> Grids | Undefined:
    """The grids `mine`, `out`'s rows at one case, hold, or undefined
    where it holds none (principles.md, under "Models and tasks"),
    `margins` as `_grid_of` reads it: where `out` has an open-value column,
    `open_grids` over the case's open values, `fields` its values at
    each field, else `resolution_grids`."""
    if not mine:
        return Undefined(NoOutput())
    if columns.open is None:
        return resolution_grids(columns.resolution, mine, margins)
    by_open = by_value(mine, columns.open)
    return open_grids(columns.resolution, [(v, v) for v in by_open],
                      by_open.__getitem__, fields, margins, {})


def open_grids[K](res_cols: tuple[ResolutionColumn, ...], groups: Sequence[tuple[Value, K]],
                  rows_of: Callable[[K], Sequence[Row]],
                  fields: FieldValues, margins: dict[int, Place | None],
                  read: dict[tuple[K, ...], Grids | Undefined]
                  ) -> Grids | Undefined:
    """`open_union` of a case's grid at each of its combinations
    (`combinations` at `fields`), `groups` each open value of its rows with the key
    `rows_of` gives those rows by: the grid at a combination is
    `resolution_grids` of the rows of the values that hold at it,
    undefined where there is none. `read` holds the grids already read, by
    the keys of their rows, so that combinations of the same rows are read
    once."""
    def at(held: tuple[int, ...]) -> Grids | Undefined:
        keys = tuple(groups[j][1] for j in held)
        got = read.get(keys)
        if got is None:
            rows = [r for k in keys for r in rows_of(k)]
            got = read[keys] = Undefined(NoOutput()) if not rows \
                else resolution_grids(res_cols, rows, margins)
        return got

    return open_union(at(held) for held in
                      combinations([v for v, _k in groups], fields))


def _fields(value: Value) -> tuple[Value, ...] | None:
    """The fields of an `OpenValue` value, one per `@open` relation; None
    for `nil`, which holds `nil` in every field. Raises ValueError for a
    value that is no record, which `OpenValue`, a record type, never
    holds (solver-file.md, under "Cases")."""
    if isinstance(value, NilValue):
        return None
    if not isinstance(value, RecordValue):
        raise ValueError(f"an `OpenValue` value is no record: {value!r}")
    return value.fields


def combinations(values: Sequence[Value], fields: FieldValues
                 ) -> list[tuple[int, ...]]:
    """The combinations of a case whose rows hold the distinct `OpenValue`
    values `values`, each as the indices of the values that hold at it:
    one combination per choice of a value at each field where some value
    holds one that is not `nil`, a field's values its values in `fields`,
    in their order (`solver.value_order.value_key`); a value holds at a combination
    where each of its fields holds `nil` or the combination's value. A
    case whose values are `nil` at every field has one combination, at
    which every value holds."""
    parts = [_fields(v) for v in values]
    width = max((len(p) for p in parts if p is not None), default=0)
    if width and len(fields) != width:
        raise ValueError(f"{len(fields)} field values for {width} fields")
    dims: list[tuple[int, list[Value]]] = []
    for i in range(width):
        if any(p is not None and not isinstance(p[i], NilValue)
               for p in parts):
            dims.append((i, sorted(fields[i], key=value_key)))
    return [tuple(j for j, p in enumerate(parts) if p is None or all(
                isinstance(p[i], NilValue) or p[i] == c
                for (i, _vs), c in zip(dims, combo, strict=True)))
            for combo in product(*(vs for _i, vs in dims))]


@quotes("principles.md", "Open parameters",
        "The output contains each grid some open value produces, and is "
        "undefined where the model is undefined at some open value.")
def open_union(per_value: Iterable[Grids | Undefined]) -> Grids | Undefined:
    """A case's output from its grids at each of its combinations of open
    values, in their order: undefined, as the first undefined combination
    is, where one is, else the distinct grids, in the order they first
    stand, with no resolution values, since a grid there may stand for
    several."""
    grids: dict[Grid, None] = {}
    for got in per_value:
        if isinstance(got, Undefined):
            return got
        grids.update(dict.fromkeys(got.grids))
    return Grids(tuple(grids))


def resolution_grids(res_cols: tuple[ResolutionColumn, ...],
                     mine: Sequence[Row],
                     margins: dict[int, Place | None]) -> Grids | Undefined:
    """The grids of `mine`, the rows of one combination of open values,
    one per resolution in the order of the resolution values
    (solver-file.md, under "Cases"), each with its resolution value where
    `out` has resolution columns `res_cols`; or undefined, with the reason
    of the first resolution that gives no total grid."""
    by_res = by_values(mine, [c.index for c in res_cols])
    grids: list[Grid] = []
    keys = sorted(by_res, key=lambda k: tuple(value_key(v) for v in k))
    for key in keys:
        grid = _grid_of(by_res[key], margins)
        if not isinstance(grid, tuple):
            return Undefined(grid)
        grids.append(grid)
    return Grids(tuple(grids), tuple(keys) if res_cols else ())
