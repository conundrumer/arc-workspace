"""Solver for ARC task 67a3c6ac — apply a d4 transform to every cell.

Rule (Datalog form):
    out(p', col) :- in(p, col), p' = apply(c.flip, p).

== Notes ==

- d4 transform is a primitive *value*, not a function. `CONSTS.flip = D4.FLIP_LR`.
  A rotated variant of this task reuses this body with a different const.

- Color is unreferenced — the rule is color-preserving.
"""

from dataclasses import dataclass

from programs.lib import D4, Grid, apply


@dataclass(frozen=True)
class Consts:
    flip: D4


CONSTS = Consts(flip=D4.FLIP_LR)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(p', col) :- in(p, col), p' = apply(c.flip, p).
    return {(apply(c.flip, p), col) for (p, col) in grid}
