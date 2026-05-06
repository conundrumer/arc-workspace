"""Shift the grid down by one row; fill the new top row with the background.

Placeholders:
- position-destructure: shift cells by 1 toward Dir.BOTTOM.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    bg: Color


CONSTS = Consts(bg=C0)


def solve(grid: Grid, c: Consts) -> Grid:
    # out((t+1, b-1, l, r), col) :- in((t, b, l, r), col), b > 0.
    shifted = {((t+1, b-1, l, r), col) for ((t, b, l, r), col) in grid if b > 0}
    # out((0, b, l, r), c.bg) :- in((0, b, l, r), _).
    top = {((0, b, l, r), c.bg) for ((t, b, l, r), _) in grid if t == 0}
    return shifted | top
