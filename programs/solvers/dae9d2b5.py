"""Combine paired cells of an input's left and right halves via a fixed (left, right, out) color table.

Placeholders:
- position-destructure: deriving half-width and rebasing each half's coords to the output bounds.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    combine: frozenset[tuple[Color, Color, Color]]


CONSTS = Consts(
    combine=frozenset({
        (C0, C0, C0),
        (C4, C0, C6),
        (C0, C3, C6),
        (C4, C3, C6),
    }),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # half_w = grid width / 2; output width = half_w.
    (w,) = {l + r + 1 for ((_, r, _, l), _) in grid}
    half_w = w // 2
    # left, right = the two halves, rebased to the same h × half_w coord system.
    left = {((t, half_w - 1 - l, b, l), col) for ((t, r, b, l), col) in grid if l < half_w}
    right = {((t, r, b, l - half_w), col) for ((t, r, b, l), col) in grid if l >= half_w}
    # out(p, c_out) :- left(p, c_l), right(p, c_r), combine(c_l, c_r, c_out).
    return {
        (p_l, c_out)
        for (p_l, c_left) in left
        for (p_r, c_right) in right if p_r == p_l
        for (a, b, c_out) in c.combine if a == c_left and b == c_right
    }
