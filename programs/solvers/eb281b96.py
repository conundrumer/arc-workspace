"""Tile the input vertically with reflected copies: c.cycles full triangle-wave bounces plus a closing row.

Placeholders:
- position-destructure: deriving height, output rows for each input row.
- imperative-iteration: K enumerated as 0..c.cycles for cycle index.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    cycles: int


CONSTS = Consts(cycles=2)


def solve(grid: Grid, c: Consts) -> Grid:
    (H,) = {t + b + 1 for ((t, b, _, _), _) in grid}
    period = 2 * (H - 1)
    out_h = c.cycles * period + 1
    # out((T_out, out_h-1-T_out, L, R), col) :- in((T, B, L, R), col), T_out = K*period + T, 0 <= T_out < out_h.
    # out((T_out, out_h-1-T_out, L, R), col) :- in((T, B, L, R), col), T_out = K*period - T, 0 <= T_out < out_h.
    # imperative-iteration: K enumerated via range().
    return {
        ((t_out, out_h - 1 - t_out, l, r), col)
        for ((t, b, l, r), col) in grid
        for t_out in (
            {k * period + t for k in range(c.cycles + 1)} |
            {k * period - t for k in range(1, c.cycles + 1)}
        )
        if 0 <= t_out < out_h
    }
