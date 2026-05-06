"""Checkerboard-of-dots pattern.

Placeholders:
- position-destructure: modulo predicate (`t % 2`, `l % 2`) on raw Position. No `wallpaper` primitive yet.

Rule (Datalog form):
    out(p, c.dot) :- in(p, _), top(p) % 2 == 1, left(p) % 2 == 1.
    out(p, c.bg)  :- in(p, _), not (top(p) % 2 == 1 and left(p) % 2 == 1).

Output is the same shape as input. Input is read only for positions; cell
colors are discarded (Pattern: "input as shape provider").

== Notes ==

- The output equals a 2×2 motif `[[bg, bg], [bg, dot]]` tiled and truncated
  to input dims. A `wallpaper` primitive would express this relationally; deferred.

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
        ((t, b, l, r), c.dot if (t % 2 == 1 and l % 2 == 1) else c.bg)
        for ((t, b, l, r), _) in grid
    }
