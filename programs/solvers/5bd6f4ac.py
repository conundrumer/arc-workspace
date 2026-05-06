"""Solver for ARC task 5bd6f4ac — output is the top-right 3×3 of input.

The output is a sub-frame of dims c.dim anchored at c.diag. Input cells
are projected into the sub-frame by matching distances to the two corner
edges (v_dir, h_dir).

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
    dim: Dim


CONSTS = Consts(diag=DiagDir.TR, dim=(3, 3))


def solve(grid: Grid, c: Consts) -> Grid:
    v_dir, h_dir = c.diag.value
    # out(O, col) :- in(P, col), frame(c.dim, O),
    #                dist(O, v_dir) = dist(P, v_dir),
    #                dist(O, h_dir) = dist(P, h_dir).
    return {(o, col)
            for (p, col) in grid
            for o in frame(c.dim)
            if dist(o, v_dir) == dist(p, v_dir)
            and dist(o, h_dir) == dist(p, h_dir)}
