"""Solver for ARC task 332efdb3 — checkerboard-of-dots pattern.

Status: placeholder — raw Position destructure with modulo predicate (no
`wallpaper` primitive yet; see docs/solvers.md).

Rule (Datalog form):
    out(p, c.dot) :- in(p, _), top(p) % 2 == 1, left(p) % 2 == 1.
    out(p, c.bg)  :- in(p, _), not (top(p) % 2 == 1 and left(p) % 2 == 1).

Output is the same shape as input. Input is read only for positions; cell
colors are discarded (Pattern: "input as shape provider").

== Notes ==

- The output equals a 2×2 motif `[[bg, bg], [bg, dot]]` tiled and truncated
  to input dims. A `wallpaper` primitive would express this relationally;
  deferred (see docs/solvers.md).

- TL-privilege caveat: the predicate uses `t` and `l` from the TL corner.
  This task's odd dimensions give the predicate 4-fold symmetry (any
  corner gives the same set), so the choice is invisible. An even-dimension
  variant would force the corner choice into consts.

- Consts: `bg` (majority color) and `dot` (cells where the predicate holds).
  Field names by role; values are this task's specific colors.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    bg: Color
    dot: Color


CONSTS = Consts(bg=C1, dot=C0)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(p, c.dot) :- in(p, _), top(p) % 2 == 1, left(p) % 2 == 1.
    # out(p, c.bg)  :- in(p, _), not (top(p) % 2 == 1 and left(p) % 2 == 1).
    return {
        ((t, r, b, l), c.dot if (t % 2 == 1 and l % 2 == 1) else c.bg)
        for ((t, r, b, l), _) in grid
    }
