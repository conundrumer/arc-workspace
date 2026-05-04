"""Solver for ARC task 6d0aefbc — output is a tiled grid-of-grids.

Rule (Datalog form):
    out(p, col) :- tile_d4(c.template, in)(p, col).

The template is a 1×2 meta-grid: IDENTITY on the left meta-cell, FLIP_LR on
the right. `tile_d4` places a d4-transformed copy of the input at each
meta-cell.

== Notes ==

- All orientation lives in `c.template` — template shape implies the axis of
  extension; d4 values per cell carry the transforms. A rotated variant
  reuses this body with a different template (e.g. 2×1 with FLIP_TB).

- Arithmetic is hidden inside `tile_d4`. Solver body is one rule.
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
