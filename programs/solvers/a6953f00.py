"""Solver for ARC task a6953f00 — 2×2 corner crop, TL or TR is valid (tiebreak).

Rule (Datalog form):
    out :- corner_view(diag, c.h, c.w)(in), choice(c.diags)(diag).

Both TL-anchored and TR-anchored 2×2 crops are valid outputs for every
example. The framework injects `choice`, runs the body once per element of
`c.diags`, and verifies that the union of branch outputs covers
{base, tiebreak alt}.

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

from programs.lib import ChoiceFn, DiagDir, Grid, corner_view


@dataclass(frozen=True)
class Consts:
    diags: frozenset[DiagDir]
    h: int
    w: int


CONSTS = Consts(diags=frozenset({DiagDir.TL, DiagDir.TR}), h=2, w=2)


def solve(grid: Grid, c: Consts, choice: ChoiceFn) -> Grid:
    diag = choice(c.diags)
    # out :- corner_view(diag, c.h, c.w)(in).
    return corner_view(grid, diag, c.h, c.w)
