"""Map the input's bg/non-bg shape to a fixed output grid."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    bg: Color
    shape_grid: frozenset[tuple[frozenset[Position], frozenset[tuple[Position, Color]]]]


CONSTS = Consts(
    bg=C0,
    shape_grid=frozenset({
        (shape([[1, 1, 0],
                [1, 0, 1],
                [0, 1, 0]]), pattern([[1]])),
        (shape([[1, 0, 1],
                [0, 1, 0],
                [1, 0, 1]]), pattern([[2]])),
        (shape([[0, 1, 1],
                [0, 1, 1],
                [1, 0, 0]]), pattern([[3]])),
        (shape([[0, 1, 0],
                [1, 1, 1],
                [0, 1, 0]]), pattern([[6]])),
    }),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # s = {p : in(p, col), col != c.bg}.
    s = frozenset(p for (p, col) in grid if col != c.bg)
    # out(p, col) :- shape_grid(s, g), g(p, col).
    return {(p, col) for (sh, g) in c.shape_grid if sh == s for (p, col) in g}
