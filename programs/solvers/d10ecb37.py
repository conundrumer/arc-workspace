"""Solver for ARC task d10ecb37 — output is the top-left 2×2 of input.

Rule (Datalog form):
    out(p, col) :- corner_view(c.diag, c.h, c.w)(in)(p, col).

The output is a corner-anchored sub-grid: anchor distances at `c.diag` are
preserved, opposite distances recomputed against (c.h, c.w).

== Notes ==

- Anchor + bounds are the entire spec — `c.diag = DiagDir.TL` here, sibling
  5bd6f4ac uses `DiagDir.TR`. Same body, different consts.
- Output dims differ from input — scaled-down (Pattern: output-dimension
  classes).
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    diag: DiagDir
    h: int
    w: int


CONSTS = Consts(diag=DiagDir.TL, h=2, w=2)


def solve(grid: Grid, c: Consts) -> Grid:
    # out :- corner_view(c.diag, c.h, c.w)(in).
    return corner_view(grid, c.diag, c.h, c.w)
