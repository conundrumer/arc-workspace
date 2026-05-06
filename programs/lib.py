"""Type vocabulary and primitives for ARC solvers.

Solver bodies treat Color as opaque: never compared by ordinal, never used
in arithmetic, never iterated as [C0, C1, ...]. The int backing exists only
so to/from JSON works.

Position is 4 distances from edges: (top, bottom, left, right). V-axis
components (top, bottom) come first, then H-axis components (left, right);
each pair sits at adjacent indices. Redundant with grid bounds; redundancy
is load-bearing — no corner privileged.

Dim is a (V-length, H-length) pair identifying a frame's dimensions.
Treated as opaque like Position; primitives consume it via Axis.

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
from typing import NamedTuple

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


type Dim = tuple[int, int]


class D4(Enum):
    """Dihedral group of the square, expressed as permutations of (t, b, l, r).

    Naming: *what swaps*, not axis of reflection. FLIP_LR swaps left/right
    distances (mirrors across the vertical axis); FLIP_TB swaps top/bottom.
    Rotations are named by direction.

    Every d4 element is a pure index permutation of the 4-distance position
    — no arithmetic, no signs. apply(d, p) is a gather.
    """

    IDENTITY      = (0, 1, 2, 3)
    FLIP_LR       = (0, 1, 3, 2)
    FLIP_TB       = (1, 0, 2, 3)
    ROT_180       = (1, 0, 3, 2)
    ROT_CW        = (2, 3, 1, 0)
    ROT_CCW       = (3, 2, 0, 1)
    FLIP_DIAG     = (2, 3, 0, 1)
    FLIP_ANTIDIAG = (3, 2, 1, 0)


class Dir(Enum):
    """One of the four edges. Values are indices into Position (top, bottom, left, right)."""

    TOP = 0
    BOTTOM = 1
    LEFT = 2
    RIGHT = 3


class Axis(Enum):
    """The two grid axes. VERTICAL spans TOP<->BOTTOM; HORIZONTAL spans LEFT<->RIGHT."""

    VERTICAL = 0
    HORIZONTAL = 1


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
    """Apply a D4 transform to a Position.

    Souffle: apply(d, p, p_out) inline.
    """
    i0, i1, i2, i3 = d.value
    return (p[i0], p[i1], p[i2], p[i3])


def dist(p: Position, d: Dir) -> int:
    """Distance from p to edge d.

    Souffle: dist(p, d, k) inline.
    """
    return p[d.value]


def opposite(d: Dir) -> Dir:
    """The Dir on the opposing edge: TOP<->BOTTOM, LEFT<->RIGHT.

    Souffle: opposite(d, opp).
    """
    return Dir(d.value ^ 1)


def axis_of(d: Dir) -> Axis:
    """The axis edge d lies on.

    Souffle: axis_of(d, a).
    """
    return Axis(d.value // 2)


class Split(NamedTuple):
    along: Position
    across: Position


def split(p: Position, axis: Axis) -> Split:
    """Decompose p into along-axis and across-axis sub-positions.

    Each sub-position is itself a Position with the perpendicular distances
    zeroed — a 1xN row (HORIZONTAL) or Mx1 column (VERTICAL) in our 4-tuple
    encoding.

    axis=HORIZONTAL: along = (0, 0, l, r)   — row-component, varies along H
                    across = (t, b, 0, 0)  — column-component, identifies row
    axis=VERTICAL:   along = (t, b, 0, 0)   — column-component, varies along V
                    across = (0, 0, l, r)  — row-component, identifies column

    Two cells share a slice along axis iff their across-components are equal.
    Equality on the across-component carries the grid-bound info (via t+b),
    so cross-grid mismatches don't false-positive.

    Souffle: Python only — Souffle solvers express slice equality directly via
    matching halves of the Position record.
    """
    if axis == Axis.HORIZONTAL:
        return Split(along=(0, 0, p[2], p[3]), across=(p[0], p[1], 0, 0))
    return Split(along=(p[0], p[1], 0, 0), across=(0, 0, p[2], p[3]))


def compose(p1: Position, p2: Position) -> Position:
    """Element-wise sum of two Positions.

    Inverse of `split` when args are a V-half and an H-half: the halves
    sum to a full Position whose frame is the V-half's height by the
    H-half's width. Same operation handles margin shifts, displacements,
    and point expansion when one operand carries signed-component deltas.

    Souffle: compose(p1, p2, p3) inline.
    """
    return (p1[0] + p2[0], p1[1] + p2[1], p1[2] + p2[2], p1[3] + p2[3])


def span(axis: Axis, length: int) -> set[Position]:
    """Positions of a 1-strip of given length along axis.

    axis=VERTICAL, length=H: H positions of an H×1 column — V-half-shaped,
    populated in (t, b) (indices 0, 1).
    axis=HORIZONTAL, length=W: W positions of a 1×W row — H-half-shaped,
    populated in (l, r) (indices 2, 3).

    Composing one of each via `compose` enumerates the cells of an H×W frame.

    Souffle: Python only — Souffle solvers use frame_pos for grid construction.
    """
    if axis == Axis.VERTICAL:
        return {(t, length - 1 - t, 0, 0) for t in range(length)}
    return {(0, 0, l, length - 1 - l) for l in range(length)}


def frame(dim: Dim) -> set[Position]:
    """All positions of a frame with given dimensions.

    Cartesian product of a V-span and an H-span composed element-wise.
    Dim's first slot is V-length, second is H-length.

    Souffle: frame_pos(v, h, p) inline (Consts helper).
    """
    v_length, h_length = dim
    return {compose(v, h)
            for v in span(Axis.VERTICAL, v_length)
            for h in span(Axis.HORIZONTAL, h_length)}


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
    (it0, ib0, il0, ir0), _ = next(iter(inner))
    hi = it0 + ib0 + 1
    wi = il0 + ir0 + 1
    return {
        (
            (mt * hi + it, mb * hi + ib, ml * wi + il, mr * wi + ir),
            col,
        )
        for ((mt, mb, ml, mr), d4) in template
        for (p, col) in inner
        for (it, ib, il, ir) in [apply(d4, p)]
    }


# ============================================================
# Helpers — builders
# ============================================================


def d4_template_from_rows(rows: list[list[D4]]) -> D4Template:
    h = len(rows)
    w = len(rows[0]) if h > 0 else 0
    return {
        ((row, h - 1 - row, col, w - 1 - col), rows[row][col])
        for row in range(h)
        for col in range(w)
    }


def color_grid(rows: list[list[int]]) -> frozenset[tuple[Position, Color]]:
    """Color-valued cells from a labeled grid; hashable for use as a relation key.

    Each cell becomes a (Position, Color) pair under 4-distance encoding
    against the grid's bounds. Returns frozenset so the result can sit
    inside a tuple in a set (shape-keyed mapping). Souffle counterpart:
    declared `color_grid(K, P, Co)` facts joined via set_eq.
    """
    h = len(rows)
    w = len(rows[0]) if h > 0 else 0
    return frozenset(
        ((row, h - 1 - row, col, w - 1 - col), Color(rows[row][col]))
        for row in range(h)
        for col in range(w)
    )


def shape_grid(rows: list[list[int]]) -> frozenset[Position]:
    """Set of on-positions from a labeled grid; hashable for use as a relation key.

    Non-zero cells contribute their Positions in 4-distance encoding. The
    encoding ties each Position to the row/col bounds, so shapes compare
    equal only if their source grids had the same dimensions.

    Distinct from color_grid: color_grid keeps the on-color in the key, so
    differently-colored silhouettes compare unequal. shape_grid is for
    tasks where the bg/non-bg silhouette alone is load-bearing.
    """
    h = len(rows)
    w = len(rows[0]) if h > 0 else 0
    return frozenset(
        (row, h - 1 - row, col, w - 1 - col)
        for row in range(h)
        for col in range(w)
        if rows[row][col] != 0
    )


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
            rows[row][col]: (row, h - 1 - row, col, w - 1 - col)
            for row in range(h)
            for col in range(w)
            if rows[row][col] != 0
        }

    in_pos = positions_by_label(input_rows)
    out_pos = positions_by_label(output_rows)
    return {(in_pos[lbl], out_pos[lbl]) for lbl in in_pos if lbl in out_pos}
