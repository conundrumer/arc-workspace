"""Self-tile: at each input cell of color C, place a copy of the input where cells of color C survive and others become bg.

Placeholders:
- position-destructure: meta and inner positions destructured for arithmetic combination.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    bg: Color


CONSTS = Consts(bg=C0)


def solve(grid: Grid, c: Consts) -> Grid:
    # n = grid side length (input is square).
    (n,) = {l + r + 1 for ((_, r, _, l), _) in grid}
    # matched((n*mt+it, n*mr+ir, n*mb+ib, n*ml+il), col) :- in((mt,mr,mb,ml), col), in((it,ir,ib,il), col).
    matched = {
        ((n * mt + it, n * mr + ir, n * mb + ib, n * ml + il), col)
        for ((mt, mr, mb, ml), col) in grid
        for ((it, ir, ib, il), col2) in grid if col2 == col
    }
    # unmatched((n*mt+it, ..., ...), c.bg) :- in((mt,mr,mb,ml), col_m), in((it,ir,ib,il), col_i), col_m != col_i.
    unmatched = {
        ((n * mt + it, n * mr + ir, n * mb + ib, n * ml + il), c.bg)
        for ((mt, mr, mb, ml), col_m) in grid
        for ((it, ir, ib, il), col_i) in grid if col_m != col_i
    }
    return matched | unmatched
