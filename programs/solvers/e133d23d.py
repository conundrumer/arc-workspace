"""Combine paired cells of the two halves of a divider-column-split input via a fixed (left, right, out) color table.

Placeholders:
- position-destructure: locating the divider column, and rebasing each half's coords to the output bounds.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    divider: Color
    combine: frozenset[tuple[Color, Color, Color]]


CONSTS = Consts(
    divider=C4,
    combine=frozenset({
        (C0, C0, C0),
        (C6, C0, C2),
        (C0, C8, C2),
        (C6, C8, C2),
    }),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # div = divider col's l-index; output width = div.
    (div,) = {l for ((_, _, _, l), col) in grid if col == c.divider}
    # left, right = the two halves, rebased to the same h × div coord system.
    left = {((t, div - 1 - l, b, l), col) for ((t, r, b, l), col) in grid if l < div}
    right = {((t, r, b, l - div - 1), col) for ((t, r, b, l), col) in grid if l > div}
    # out(p, c_out) :- left(p, c_l), right(p, c_r), combine(c_l, c_r, c_out).
    return {
        (p_l, c_out)
        for (p_l, c_left) in left
        for (p_r, c_right) in right if p_r == p_l
        for (a, b, c_out) in c.combine if a == c_left and b == c_right
    }
