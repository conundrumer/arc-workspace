"""Solver for ARC task c9e6f938 — horizontal mirror double-width; same rule as 6d0aefbc.

See 6d0aefbc.py. This task uses the same template `[[IDENTITY, FLIP_LR]]`.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    template: D4Template


CONSTS = Consts(template=d4_template_from_rows([[D4.IDENTITY, D4.FLIP_LR]]))


def solve(grid: Grid, c: Consts) -> Grid:
    # out :- tile_d4(c.template, in).
    return tile_d4(c.template, grid)
