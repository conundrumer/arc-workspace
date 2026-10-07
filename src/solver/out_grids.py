"""The grids `out`'s rows hold: the columns of `out`, the cell and the
grid size a `Position` value gives, and the grids a case's rows give, or
why they give none."""

from collections.abc import Sequence
from dataclasses import dataclass

from engine import (
    Grid,
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
from solver.aggregate import (
    TOP,
)
from solver.model import (
    Case,
)
from solver.outcome import Grids
from solver.run_parts import value_key
from solver.vocabulary import (
    CHOICE,
    OUTPUT,
    TIEBREAK_RESOLUTION,
)
from solver.witness import (
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


def out_columns(program: Program) -> tuple[int | None, int | None]:
    """The case column and the resolution column of `out`, by type
    (solver-file.md, under "Cases" and "Alt outputs"); None where `out` has
    none."""
    decl = out_decl(program)
    if decl is None:
        return None, None
    types = [c.type.text for c in decl.columns]
    case = types.index(CHOICE) if CHOICE in types else None
    res = (types.index(TIEBREAK_RESOLUTION)
           if TIEBREAK_RESOLUTION in types else None)
    return case, res


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


def grids_of(program: Program, rows: Rows, case: Case) -> Grids | Undefined:
    """The grids `out`'s rows hold at `case`, one per resolution in the order
    of the resolution values (solver-file.md, under "Cases"), or undefined,
    with the reason of the first resolution that gives no total grid
    (principles.md, under "Models and tasks")."""
    case_col, res_col = out_columns(program)
    return case_grids(res_col, [r for r in rows if case_col is None or case.base is None
                                or r[case_col] == case.base], {})


def rows_by_base(rows: Rows, case_col: int | None) -> dict[Value, list[Row]]:
    """`out`'s rows by the base in their case column, each list in the
    rows' order; empty where `out` has no case column."""
    return {} if case_col is None else _by_value(rows, case_col)


def _by_value(rows: Sequence[Row], col: int) -> dict[Value, list[Row]]:
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


def case_grids(res_col: int | None, mine: Sequence[Row],
           margins: dict[int, Place | None]) -> Grids | Undefined:
    """`grids_of` over the rows of one case, with `res_col` `out`'s
    resolution column and `margins` as `_grid_of` reads it."""
    by_res: dict[Value | None, list[Row]] = (
        {None: list(mine)} if res_col is None
        else {k: v for k, v in _by_value(mine, res_col).items()})
    if not mine:
        return Undefined(NoOutput())
    grids: list[Grid] = []
    keys = sorted(by_res, key=lambda v: () if v is None else value_key(v))
    for key in keys:
        grid = _grid_of(by_res[key], margins)
        if not isinstance(grid, tuple):
            return Undefined(grid)
        grids.append(grid)
    return Grids(tuple(grids), tuple(k for k in keys if k is not None))
