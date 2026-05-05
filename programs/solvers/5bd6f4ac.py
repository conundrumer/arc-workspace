"""Solver for ARC task 5bd6f4ac — output is the top-right 3×3 of input.

The output is a corner-anchored sub-grid: anchor distances at `c.diag` are
preserved, opposite distances recomputed against (c.h, c.w).

Placeholders:
- position-destructure: corner-anchored rebase; opposite-side distances recomputed by hand.

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
    v_dir, h_dir = c.diag.value
    v_opp, h_opp = opposite(v_dir), opposite(h_dir)
    def anchored(p):
        new_p = list(p)
        new_p[v_opp.value] = c.h - 1 - p[v_dir.value]
        new_p[h_opp.value] = c.w - 1 - p[h_dir.value]
        return tuple(new_p)
    # out(anchored(P), col) :- in(P, col), dist(P, v_dir) < c.h, dist(P, h_dir) < c.w.
    return {(anchored(p), col) for (p, col) in grid
            if dist(p, v_dir) < c.h and dist(p, h_dir) < c.w}
