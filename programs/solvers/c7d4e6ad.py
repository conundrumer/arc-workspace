"""Solver for ARC task c7d4e6ad — substitute a color with the row's anchor cell.

Rule (Souffle form):
    out(p, repl) :- in(p, x), targets(x),
                    in(p_anchor, repl), dist(p_anchor, anchor) == 0,
                    split(p, axis_of(anchor))        = (_, across),
                    split(p_anchor, axis_of(anchor)) = (_, across).
    out(p, col)  :- in(p, col), !targets(col).

The two `split()` calls bind the same `across` variable — that shared
binding is the per-row scoping. For anchor=LEFT, axis=HORIZONTAL, "same
across" = same column-component = same row.

== Notes ==

- Consts: `targets: set[Color]` (unary relation, colors flagged for
  substitution) and `anchor: Dir` (the edge of the row supplying the
  replacement). A rotated variant (anchor=TOP) reuses this body verbatim.

- Replacement is *derived*, not a const — `in(p_anchor, repl)` joined via
  shared across-component.

- Position access goes through `dist` and `split` — no raw destructure.
  Across-component equality carries grid-bound info, so positions from
  different-sized grids correctly compare as not-same-row.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    targets: set[Color]
    anchor: Dir


CONSTS = Consts(targets={C5}, anchor=Dir.LEFT)


def solve(grid: Grid, c: Consts) -> Grid:
    a = axis_of(c.anchor)

    # anchor_cells(p, col) :- in(p, col), dist(p, c.anchor) == 0.
    anchor_cells = {(p, col) for (p, col) in grid if dist(p, c.anchor) == 0}

    # matched(p, repl) :- in(p, x), targets(x),
    #                    anchor_cells(p_anchor, repl),
    #                    split(p, a)        = (_, across),
    #                    split(p_anchor, a) = (_, across).
    matched = {
        (p, repl)
        for (p, col) in grid if col in c.targets
        for (p_anchor, repl) in anchor_cells
        if split(p, a).across == split(p_anchor, a).across
    }

    # unmatched(p, col) :- in(p, col), !targets(col).
    unmatched = {(p, col) for (p, col) in grid if col not in c.targets}

    return matched | unmatched
