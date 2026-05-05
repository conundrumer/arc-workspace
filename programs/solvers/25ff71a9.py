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
    # out((t+1, r, b-1, l), col) :- in((t, r, b, l), col), b > 0.
    shifted = {((t+1, r, b-1, l), col) for ((t, r, b, l), col) in grid if b > 0}
    # out((0, r, b, l), c.bg) :- in((0, r, b, l), _).
    top = {((0, r, b, l), c.bg) for ((t, r, b, l), _) in grid if t == 0}
    return shifted | top
