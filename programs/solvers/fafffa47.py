"""Combine paired cells of an input's top and bottom halves via a fixed (top, bottom, out) color table.

Placeholders:
- position-destructure: deriving half-height and rebasing each half's coords to the output bounds.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    combine: frozenset[tuple[Color, Color, Color]]


CONSTS = Consts(
    combine=frozenset({
        (C0, C0, C2),
        (C9, C0, C0),
        (C0, C1, C0),
        (C9, C1, C0),
    }),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # half_h = grid height / 2; output height = half_h.
    (h,) = {t + b + 1 for ((t, b, _, _), _) in grid}
    half_h = h // 2
    # top, bottom = the two halves, rebased to the same half_h × w coord system.
    top = {((t, half_h - 1 - t, l, r), col) for ((t, b, l, r), col) in grid if t < half_h}
    bottom = {((t - half_h, b, l, r), col) for ((t, b, l, r), col) in grid if t >= half_h}
    # out(p, c_out) :- top(p, c_t), bottom(p, c_b), combine(c_t, c_b, c_out).
    return {
        (p_t, c_out)
        for (p_t, c_top) in top
        for (p_b, c_bot) in bottom if p_b == p_t
        for (a, b, c_out) in c.combine if a == c_top and b == c_bot
    }
