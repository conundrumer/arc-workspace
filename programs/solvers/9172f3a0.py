"""Scale the input by a fixed integer factor: each cell becomes an s × s block of the same color.

Placeholders:
- position-destructure: per-component arithmetic for s-scale upsampling.
- consts-helper-in-body: `shape_grid()` in body enumerates the s×s inner block.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    scale: int


CONSTS = Consts(scale=3)


def solve(grid: Grid, c: Consts) -> Grid:
    # Inner positions of the s × s block, in 4-distance.
    inner = shape_grid([[1] * c.scale for _ in range(c.scale)])
    # out((s*t+it, s*b+ib, s*l+il, s*r+ir), col) :- in((t,b,l,r), col), inner((it,ib,il,ir)).
    return {
        ((c.scale * t + it, c.scale * b + ib, c.scale * l + il, c.scale * r + ir), col)
        for ((t, b, l, r), col) in grid
        for (it, ib, il, ir) in inner
    }
