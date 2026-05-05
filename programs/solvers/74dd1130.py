"""Apply a D4 transform to every cell."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    transform: D4


CONSTS = Consts(transform=D4.FLIP_DIAG)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(p', col) :- in(p, col), p' = apply(c.transform, p).
    return {(apply(c.transform, p), col) for (p, col) in grid}
