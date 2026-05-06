"""Combine paired cells of an input's left and right halves via a fixed (left, right, out) color table."""

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
    (w,) = {dist(p, Dir.LEFT) + dist(p, Dir.RIGHT) + 1 for (p, _) in grid}
    half_w = w // 2
    # left, right = the two halves, rebased into an h × half_w frame by chopping the opposite-side margin.
    chop_right = (0, 0, 0, -half_w)
    chop_left = (0, 0, -half_w, 0)
    left = {(compose(p, chop_right), col) for (p, col) in grid if dist(p, Dir.LEFT) < half_w}
    right = {(compose(p, chop_left), col) for (p, col) in grid if dist(p, Dir.LEFT) >= half_w}
    # out(p, c_out) :- left(p, c_l), right(p, c_r), combine(c_l, c_r, c_out).
    return {
        (p_l, c_out)
        for (p_l, c_left) in left
        for (p_r, c_right) in right if p_r == p_l
        for (a, b, c_out) in c.combine if a == c_left and b == c_right
    }
