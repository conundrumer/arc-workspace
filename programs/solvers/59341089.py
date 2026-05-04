"""Solver for ARC task 59341089 — 4× width, alternating horizontal flips per row.

Rule (Datalog form):
    out(p, col) :- tile_d4(c.template, in)(p, col).

The template is a 1×4 meta-grid: [FLIP_LR, IDENTITY, FLIP_LR, IDENTITY]. Each
meta-cell places a d4-transformed copy of the input — every other column-band
is mirrored.

== Notes ==

- Sibling of 6d0aefbc: identical body, wider template (1×4 vs 1×2). Confirms
  the orientation-as-const pattern carries across template widths unchanged.
- All d4 values are in {IDENTITY, FLIP_LR}, so tile_d4's preserved-dims
  precondition holds without requiring a square inner.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    template: D4Template


CONSTS = Consts(
    template=d4_template_from_rows(
        [[D4.FLIP_LR, D4.IDENTITY, D4.FLIP_LR, D4.IDENTITY]]
    )
)


def solve(grid: Grid, c: Consts) -> Grid:
    # out :- tile_d4(c.template, in).
    return tile_d4(c.template, grid)
