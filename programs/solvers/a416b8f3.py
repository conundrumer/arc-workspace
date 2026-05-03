"""Solver for ARC task a416b8f3 — duplicate input horizontally (no flip).

Rule (Datalog form):
    out(p, col) :- tile_d4(c.template, in)(p, col).

Template: 1×2 of [IDENTITY, IDENTITY]. The d4-template abstraction covers
"concat unchanged" naturally — the d4 values are irrelevant; what does the
work is the meta-grid layout.
"""

from dataclasses import dataclass

from programs.lib import D4, D4Template, Grid, d4_template_from_rows, tile_d4


@dataclass(frozen=True)
class Consts:
    template: D4Template


CONSTS = Consts(template=d4_template_from_rows([[D4.IDENTITY, D4.IDENTITY]]))


def solve(grid: Grid, c: Consts) -> Grid:
    # out :- tile_d4(c.template, in).
    return tile_d4(c.template, grid)
