"""Solver for ARC task a6953f00 — 2×2 corner crop, TL or TR is valid (tiebreak).

Both TL-anchored and TR-anchored 2×2 crops are valid outputs for every
example. The framework injects `choice`, runs the body once per element of
`c.diags`, and verifies that the union of branch outputs covers
{base, tiebreak alt}.

Placeholders:
- position-destructure: corner-anchored rebase; opposite-side distances recomputed by hand.

== Notes ==

- The original "width parity selects corner" reading was fitted to data
  (4×4 → TR, 3×3 → TL, …); the canonical patch declares both corners as
  tiebreak alts on every example, making the symmetry explicit.
- First solver to use the choice-fn injection. Solver shape: solve takes
  `choice` as a third arg; framework discovers the choice domain in one
  pass, then enumerates branches via cartesian product.
- `c.diags` is the choice domain — TL and TR. Mirrors Souffle's
  choice-domain non-determinism.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    diags: frozenset[DiagDir]
    h: int
    w: int


CONSTS = Consts(diags=frozenset({DiagDir.TL, DiagDir.TR}), h=2, w=2)


def solve(grid: Grid, c: Consts, choice: ChoiceFn) -> Grid:
    diag = choice(c.diags)
    v_dir, h_dir = diag.value
    v_opp, h_opp = opposite(v_dir), opposite(h_dir)
    def anchored(p):
        new_p = list(p)
        new_p[v_opp.value] = c.h - 1 - p[v_dir.value]
        new_p[h_opp.value] = c.w - 1 - p[h_dir.value]
        return tuple(new_p)
    # out(anchored(P), col) :- in(P, col), dist(P, v_dir) < c.h, dist(P, h_dir) < c.w.
    return {(anchored(p), col) for (p, col) in grid
            if dist(p, v_dir) < c.h and dist(p, h_dir) < c.w}
