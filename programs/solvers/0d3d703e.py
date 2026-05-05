"""Recolor cells through a fixed color involution."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    recolor: frozenset[tuple[Color, Color]]


CONSTS = Consts(
    recolor=frozenset({
        (C1, C5), (C5, C1),
        (C2, C6), (C6, C2),
        (C3, C4), (C4, C3),
        (C8, C9), (C9, C8),
    }),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(p, col2) :- in(p, col1), recolor(col1, col2).
    return {(p, col2) for (p, col1) in grid for (a, col2) in c.recolor if a == col1}
