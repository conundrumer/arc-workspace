"""Solver for ARC task 68b16354 — vertical flip.

Rule (Souffle form):
    out(apply(c.flip, P), col) :- in(P, col).

Per-cell d4 transform applied to the entire grid; no extraction or
selection step.

== Notes ==

- Body shape matches be03b35f's rotation step, minus the corner-anchored
  filter — here the transform applies to the whole grid. Second occurrence of the
  per-cell `apply(d4, p)` over Cells. The lift candidate `transform(
  cells: Cells[*Xs], d: D4) -> Cells[*Xs]` is now at the
  resist-abstraction trigger; deferred for user direction.

- Consts: `flip: D4 = FLIP_TB`. A horizontal flip would swap the const
  to FLIP_LR without touching the body (Object Principle 6).

- Output dims = input dims (FLIP_TB preserves dims; same for FLIP_LR /
  ROT_180; rotations swap H↔W on non-square but D4-on-square sidesteps).
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    flip: D4


CONSTS = Consts(flip=D4.FLIP_TB)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(apply(c.flip, P), col) :- in(P, col).
    return {(apply(c.flip, p), col) for (p, col) in grid}
