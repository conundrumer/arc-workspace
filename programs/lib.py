"""Type vocabulary and primitives for ARC solvers.

Solver bodies treat Color as opaque: never compared by ordinal, never used
in arithmetic, never iterated as [C0, C1, ...]. The int backing exists only
so to/from JSON works.

Position is 4 distances from edges: (top, right, bottom, left). Redundant
with grid bounds; redundancy is load-bearing — no corner privileged.

Cells[*Xs] is a Position-keyed relation with any number of value columns.
Grid is the Color-valued specialization (set of (Position, Color)) for
solver in/out; D4Template is the D4-valued specialization. Other value-
column shapes parameterize through *Xs without touching call sites.

Spatial primitives appear here once they're load-bearing across solvers.
D4 transforms entered immediately because encoding orientation in a
function name (e.g. flip_h) bakes orientation into the solver body.
"""

from collections.abc import Callable
from enum import Enum

type ChoiceFn = Callable[[frozenset], object]


# ============================================================
# Core types
# ============================================================


class Color(Enum):
    C0 = 0
    C1 = 1
    C2 = 2
    C3 = 3
    C4 = 4
    C5 = 5
    C6 = 6
    C7 = 7
    C8 = 8
    C9 = 9


# Bare-name aliases for color literals — avoids `Color.` namespace noise in
# mapping tables. `Color` is still used for type annotations.
C0, C1, C2, C3, C4, C5, C6, C7, C8, C9 = Color


type Position = tuple[int, int, int, int]


class D4(Enum):
    """Dihedral group of the square, expressed as permutations of (t, r, b, l).

    Naming: *what swaps*, not axis of reflection. FLIP_LR swaps left/right
    distances (mirrors across the vertical axis); FLIP_TB swaps top/bottom.
    Rotations are named by direction.

    Every d4 element is a pure index permutation of the 4-distance position
    — no arithmetic, no signs. apply(d, p) is a gather.
    """

    IDENTITY = (0, 1, 2, 3)
    FLIP_LR = (0, 3, 2, 1)
    FLIP_TB = (2, 1, 0, 3)
    ROT_180 = (2, 3, 0, 1)
    ROT_CW = (3, 0, 1, 2)
    ROT_CCW = (1, 2, 3, 0)
    FLIP_DIAG = (3, 2, 1, 0)
    FLIP_ANTIDIAG = (1, 0, 3, 2)


class Dir(Enum):
    """One of the four edges. Values are indices into Position (top, right, bottom, left)."""

    TOP = 0
    RIGHT = 1
    BOTTOM = 2
    LEFT = 3


class Axis(Enum):
    """The two grid axes. HORIZONTAL spans LEFT<->RIGHT; VERTICAL spans TOP<->BOTTOM."""

    HORIZONTAL = 0
    VERTICAL = 1


class DiagDir(Enum):
    """One of the four corners. Values are (vertical, horizontal) Dir pairs.

    The vertical Dir is TOP or BOTTOM; the horizontal is LEFT or RIGHT. Each
    diag identifies a corner via the two edges it sits on — distances to those
    two edges point at the corner, the other two point away from it. Value
    carries structure so primitives consume the component Dirs directly.
    """

    TL = (Dir.TOP, Dir.LEFT)
    TR = (Dir.TOP, Dir.RIGHT)
    BL = (Dir.BOTTOM, Dir.LEFT)
    BR = (Dir.BOTTOM, Dir.RIGHT)


type Cells[*Xs] = set[tuple[Position, *Xs]]
type Grid = Cells[Color]
type D4Template = Cells[D4]


# ============================================================
# Core operations
# ============================================================


def apply(d: D4, p: Position) -> Position:
    i0, i1, i2, i3 = d.value
    return (p[i0], p[i1], p[i2], p[i3])


def dist(p: Position, d: Dir) -> int:
    """Distance from p to edge d."""
    return p[d.value]


def opposite(d: Dir) -> Dir:
    """The Dir on the opposing edge: TOP<->BOTTOM, LEFT<->RIGHT."""
    return Dir((d.value + 2) % 4)


def axis_of(d: Dir) -> Axis:
    """The axis edge d lies on."""
    return Axis.HORIZONTAL if d in (Dir.LEFT, Dir.RIGHT) else Axis.VERTICAL


def split(p: Position, axis: Axis) -> tuple[Position, Position]:
    """Decompose p into (along-axis, across-axis) sub-positions.

    Each sub-position is itself a Position with the perpendicular distances
    zeroed — a 1xN row (HORIZONTAL) or Mx1 column (VERTICAL) in our 4-tuple
    encoding.

    axis=HORIZONTAL: along = (0, r, 0, l)   — row-component, varies along H
                    across = (t, 0, b, 0)  — column-component, identifies row
    axis=VERTICAL:   along = (t, 0, b, 0)   — column-component, varies along V
                    across = (0, r, 0, l)  — row-component, identifies column

    Two cells share a slice along axis iff their across-components are equal.
    Equality on the across-component carries the grid-bound info (via t+b),
    so cross-grid mismatches don't false-positive.
    """
    if axis == Axis.HORIZONTAL:
        return ((0, p[1], 0, p[3]), (p[0], 0, p[2], 0))
    return ((p[0], 0, p[2], 0), (0, p[1], 0, p[3]))


def tile_d4(template: D4Template, inner: Grid) -> Grid:
    """Place a d4-transformed copy of `inner` at each meta-cell of `template`.

    Output dims = (template_h * inner_h, template_w * inner_w). Assumes every
    d4 value in `template` preserves `inner`'s dimensions — i.e. `inner` is
    square, or transforms are limited to {IDENTITY, FLIP_LR, FLIP_TB, ROT_180}.
    A rotation that swaps Hi<->Wi on a non-square inner would produce a
    mismatched tiling; defer until a task forces it.

    `tile` (without suffix) is reserved for a more general operation if/when
    templates of other value types appear.
    """
    if not inner or not template:
        return set()
    (it0, ir0, ib0, il0), _ = next(iter(inner))
    hi = it0 + ib0 + 1
    wi = il0 + ir0 + 1
    return {
        (
            (mt * hi + it, mr * wi + ir, mb * hi + ib, ml * wi + il),
            col,
        )
        for ((mt, mr, mb, ml), d4) in template
        for (p, col) in inner
        for (it, ir, ib, il) in [apply(d4, p)]
    }


def corner_view[*Xs](cells: Cells[*Xs], diag: DiagDir, h: int, w: int) -> Cells[*Xs]:
    """The h×w sub-grid whose contents match the `diag` corner of `cells`.

    Anchor-side distances are kept; opposite-side distances are recomputed
    against the new (h, w) bounds. Cells outside the corner region are
    dropped. Non-Position columns flow through transparently — Cells[*Xs]
    in, Cells[*Xs] out.
    """
    v_dir, h_dir = diag.value
    v_opp = opposite(v_dir)
    h_opp = opposite(h_dir)
    out: set = set()
    for (pos, *rest) in cells:
        v_kept = pos[v_dir.value]
        h_kept = pos[h_dir.value]
        if v_kept >= h or h_kept >= w:
            continue
        new_p = [0, 0, 0, 0]
        new_p[v_dir.value] = v_kept
        new_p[h_dir.value] = h_kept
        new_p[v_opp.value] = h - 1 - v_kept
        new_p[h_opp.value] = w - 1 - h_kept
        out.add(((new_p[0], new_p[1], new_p[2], new_p[3]), *rest))
    return out


# ============================================================
# Helpers — builders and JSON bridge
# ============================================================


def d4_template_from_rows(rows: list[list[D4]]) -> D4Template:
    h = len(rows)
    w = len(rows[0]) if h > 0 else 0
    return {
        ((r, w - 1 - c, h - 1 - r, c), rows[r][c])
        for r in range(h)
        for c in range(w)
    }


def to_relational(rows: list[list[int]]) -> Grid:
    h = len(rows)
    w = len(rows[0]) if h > 0 else 0
    return {
        ((r, w - 1 - c, h - 1 - r, c), Color(rows[r][c]))
        for r in range(h)
        for c in range(w)
    }


def pattern(rows: list[list[int]]) -> frozenset[tuple[Position, Color]]:
    """Hashable Cells value for use as a relation key.

    Same Position math as to_relational; returns frozenset so the result
    can sit inside a tuple in a set (shape-keyed mapping). Souffle
    counterpart: declared `pattern(K, Al, Co)` facts joined via set_eq
    (see docs/solvers.md, Souffle alignment).
    """
    return frozenset(to_relational(rows))


def position_mapping(
    input_rows: list[list[int]],
    output_rows: list[list[int]],
) -> set[tuple[Position, Position]]:
    """Pair positions in two labeled grids by matching label.

    Each non-zero int in `input_rows` and `output_rows` is a label;
    matching labels identify a position pair. Labels are arbitrary
    positive ints — no Color cap. Zero is always treated as bg (no
    pairing); convention is "don't use 0 as a label."

    Used to declare a Position-keyed substitution table (the rule is
    `out(P_out, col) :- in(P_in, col), mapping(P_in, P_out)`) where
    the mapping's spatial structure is more readable as two labeled
    grids than as a list of 4-tuple pairs.
    """
    def positions_by_label(rows: list[list[int]]) -> dict[int, Position]:
        h = len(rows)
        w = len(rows[0]) if rows else 0
        return {
            rows[r][c]: (r, w - 1 - c, h - 1 - r, c)
            for r in range(h)
            for c in range(w)
            if rows[r][c] != 0
        }

    in_pos = positions_by_label(input_rows)
    out_pos = positions_by_label(output_rows)
    return {(in_pos[lbl], out_pos[lbl]) for lbl in in_pos if lbl in out_pos}


def from_relational(g: Grid) -> list[list[int]]:
    if not g:
        return []
    bounds = {(t + b + 1, l + r + 1) for ((t, r, b, l), _) in g}
    if len(bounds) != 1:
        raise ValueError(f"inconsistent grid bounds across positions: {bounds}")
    h, w = next(iter(bounds))
    by_cell: dict[tuple[int, int], int] = {}
    for (t, r, b, l), col in g:
        if t < 0 or r < 0 or b < 0 or l < 0:
            raise ValueError(f"negative position component: ({t}, {r}, {b}, {l})")
        if (t, l) in by_cell:
            raise ValueError(
                f"duplicate cell at (top={t}, left={l}): "
                f"Color({by_cell[(t, l)]}) and Color({col.value})"
            )
        by_cell[(t, l)] = col.value
    if len(by_cell) != h * w:
        raise ValueError(f"coverage: {len(by_cell)} cells, expected {h * w} for {h}x{w}")
    out = [[0] * w for _ in range(h)]
    for (t, l), v in by_cell.items():
        out[t][l] = v
    return out
