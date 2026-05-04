"""VERTICAL XOR fold of input halves.

Placeholders:
- position-destructure: layout split. Conceptual primitive is "split into halves along an axis (with optional margin)" — same family entry as 34b99a2b / 5d2a5c43 (HORIZONTAL fold *with* a divider). This is the first VERTICAL non-margin sample.

Rule (Souffle form):
    top(P, C) :- in(P, C), within `c.half_h` of TOP edge, repositioned to
                  the half-height bound.
    bot(P, C) :- in(P, C), within `c.half_h` of BOTTOM edge, repositioned
                  symmetrically so it aligns with `top` by Position.
    out(P, T) :- top(P, t_col), bot(P, b_col), mapping(t_col, b_col, T).

The `mapping` relation enumerates `(top_color, bottom_color) → out_color`
— actual data colors, no boolean projection (Object Principle 9). The
XOR pattern is implicit in the table's rows.

== Notes ==

- Same-rule kinship: 34b99a2b (HORIZONTAL XOR fold with 1-col divider)
  and 5d2a5c43 (HORIZONTAL OR fold). All three share the
  halves-fold-with-mapping shape; this one differs in axis (VERTICAL)
  and has no divider.

- Top fill color is C9, bottom is C4, output marker is C6. The mapping
  embeds these directly; a sibling task with different colors but the
  same rule would just swap the relation's rows.

- Lift candidate is unchanged from 34b99a2b's docstring: an axis-parameterized
  halves-fold with optional margin width.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    half_h: int
    mapping: set[tuple[Color, Color, Color]]


CONSTS = Consts(
    half_h=3,
    mapping={
        (C0, C0, C0),  # both empty → C0
        (C9, C0, C6),  # top only filled → C6
        (C0, C4, C6),  # bottom only filled → C6
        (C9, C4, C0),  # both filled → C0
    },
)


def solve(grid: Grid, c: Consts) -> Grid:
    half = c.half_h

    # Top half: cells within `half` of the TOP edge; output bottom-distance
    # rebuilt against the smaller bound.
    top = {
        ((t, r, half - 1 - t, l), col)
        for ((t, r, _, l), col) in grid
        if t < half
    }

    # Bottom half: cells within `half` of the BOTTOM edge; output
    # top-distance rebuilt symmetrically so it aligns with `top` by Position.
    bot = {
        ((half - 1 - b, r, b, l), col)
        for ((_, r, b, l), col) in grid
        if b < half
    }

    # out(p, t) :- top(p, top_col), bot(p, bot_col), mapping(top_col, bot_col, t).
    return {
        (p, out_c)
        for (p, t_col) in top
        for (p2, b_col) in bot
        if p == p2
        for (tk, bk, out_c) in c.mapping
        if t_col == tk and b_col == bk
    }
