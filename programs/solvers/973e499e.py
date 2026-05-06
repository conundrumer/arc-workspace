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
    (n,) = {l + r + 1 for ((_, _, l, r), _) in grid}
    # matched((n*mt+it, n*mb+ib, n*ml+il, n*mr+ir), col) :- in((mt,mb,ml,mr), col), in((it,ib,il,ir), col).
    matched = {
        ((n * mt + it, n * mb + ib, n * ml + il, n * mr + ir), col)
        for ((mt, mb, ml, mr), col) in grid
        for ((it, ib, il, ir), col2) in grid if col2 == col
    }
    # unmatched((n*mt+it, ..., ...), c.bg) :- in((mt,mb,ml,mr), col_m), in((it,ib,il,ir), col_i), col_m != col_i.
    unmatched = {
        ((n * mt + it, n * mb + ib, n * ml + il, n * mr + ir), c.bg)
        for ((mt, mb, ml, mr), col_m) in grid
        for ((it, ib, il, ir), col_i) in grid if col_m != col_i
    }
    return matched | unmatched
