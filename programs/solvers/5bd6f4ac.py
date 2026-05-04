"""Solver for ARC task 5bd6f4ac — output is the top-right 3×3 of input.

Rule (Datalog form):
    out(p, col) :- corner_view(c.diag, c.h, c.w)(in)(p, col).

The output is a corner-anchored sub-grid: anchor distances at `c.diag` are
preserved, opposite distances recomputed against (c.h, c.w).

== Notes ==

- Sibling of d10ecb37; same body, differs only in `c.diag` (TR vs TL).
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


CONSTS = Consts(diag=DiagDir.TR, h=3, w=3)


def solve(grid: Grid, c: Consts) -> Grid:
    # out :- corner_view(c.diag, c.h, c.w)(in).
    return corner_view(grid, c.diag, c.h, c.w)
