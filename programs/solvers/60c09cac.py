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


CONSTS = Consts(scale=2)


def solve(grid: Grid, c: Consts) -> Grid:
    # Inner positions of the s × s block, in 4-distance.
    inner = shape_grid([[1] * c.scale for _ in range(c.scale)])
    # out((s*t+it, s*r+ir, s*b+ib, s*l+il), col) :- in((t,r,b,l), col), inner((it,ir,ib,il)).
    return {
        ((c.scale * t + it, c.scale * r + ir, c.scale * b + ib, c.scale * l + il), col)
        for ((t, r, b, l), col) in grid
        for (it, ir, ib, il) in inner
    }
