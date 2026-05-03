"""Solver for ARC task 8be77c9e — vertical flip-double; same rule as 6fa7a44f.

Rule (Datalog form):
    out(p, col) :- tile_d4(c.template, in)(p, col).

Template: 2×1 of [IDENTITY, FLIP_TB]. Bit-for-bit identical body and CONSTS
to 6fa7a44f — two distinct task IDs share the same rule.
"""

from dataclasses import dataclass

from programs.lib import D4, D4Template, Grid, d4_template_from_rows, tile_d4


@dataclass(frozen=True)
class Consts:
    template: D4Template


CONSTS = Consts(template=d4_template_from_rows([[D4.IDENTITY], [D4.FLIP_TB]]))


def solve(grid: Grid, c: Consts) -> Grid:
    # out :- tile_d4(c.template, in).
    return tile_d4(c.template, grid)
