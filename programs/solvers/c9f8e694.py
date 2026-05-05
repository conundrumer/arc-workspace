"""Solver for ARC task c9f8e694 — same rule as c7d4e6ad: LEFT-anchored row substitution.

Conceptual rule is identical to c7d4e6ad: target cells (C5) are substituted
with the row's LEFT-edge color. The TS reference for this task expresses
the anchor by content (`row.find(c => c !== C0 && c !== C5)`); the
data places that anchor cell at the LEFT edge in every row, so the
content-search and the position-search yield the same color. Body
matches c7d4e6ad verbatim — different ARC tasks, same rule.

(See c7d4e6ad.py for the rule's Souffle form and notes.)

== Notes ==

- Same body as c7d4e6ad. Two witnesses of one rule.
- Equivalence is data-dependent: the rules would diverge only on rows
  where the LEFT-edge cell is C0 or C5 *and* there's a non-target,
  non-background color elsewhere in the row. No such row appears in
  either task's data.
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
