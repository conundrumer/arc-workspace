"""Combine paired cells of the two halves of a divider-split input via a fixed (top, bot, out) color table.

Placeholders:
- position-destructure: locating the divider row, and rebasing each half's coords to the output bounds.
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
        (C2, C2, C0),
        (C0, C2, C3),
        (C2, C0, C3),
    }),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # div = divider row's t-index; output height = div.
    (div,) = {t for ((t, _, _, _), col) in grid if col == c.divider}
    # top, bot = the two halves, rebased to the same h_out × w coord system.
    top = {((t, div - 1 - t, l, r), col) for ((t, b, l, r), col) in grid if t < div}
    bot = {((t - div - 1, b, l, r), col) for ((t, b, l, r), col) in grid if t > div}
    # out(p, c_out) :- top(p, c_top), bot(p, c_bot), combine(c_top, c_bot, c_out).
    return {
        (p_t, c_out)
        for (p_t, c_top) in top
        for (p_b, c_bot) in bot if p_b == p_t
        for (a, b, c_out) in c.combine if a == c_top and b == c_bot
    }
