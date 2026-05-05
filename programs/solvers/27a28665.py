"""Map the input's bg/non-bg silhouette to a fixed output grid."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    bg: Color
    output_for_shape: frozenset[tuple[frozenset[Position], frozenset[tuple[Position, Color]]]]


CONSTS = Consts(
    bg=C0,
    output_for_shape=frozenset({
        (shape_grid([[1, 1, 0],
                     [1, 0, 1],
                     [0, 1, 0]]), color_grid([[1]])),
        (shape_grid([[1, 0, 1],
                     [0, 1, 0],
                     [1, 0, 1]]), color_grid([[2]])),
        (shape_grid([[0, 1, 1],
                     [0, 1, 1],
                     [1, 0, 0]]), color_grid([[3]])),
        (shape_grid([[0, 1, 0],
                     [1, 1, 1],
                     [0, 1, 0]]), color_grid([[6]])),
    }),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # s = {p : in(p, col), col != c.bg}.
    s = frozenset(p for (p, col) in grid if col != c.bg)
    # out(p, col) :- output_for_shape(s, g), g(p, col).
    return {(p, col) for (sh, g) in c.output_for_shape if sh == s for (p, col) in g}
