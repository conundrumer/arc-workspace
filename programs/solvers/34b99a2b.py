"""Fold halves about a divider via color mapping.

Placeholders:
- position-destructure: layout split. Conceptual primitive is "split into halves along an axis with a margin (the divider)" — same family as slab/stride. Lift on a third layout occurrence.

Rule (Souffle form):
    left(p, c)  :- in(p, c), within `c.half_w` of one edge, repositioned.
    right(p, c) :- in(p, c), within `c.half_w` of the opposite edge,
                   repositioned to align with `left` by Position.
    out(p, t) :- left(p, l), right(p, r), mapping(l, r, t).

The `mapping` relation enumerates the (left_color, right_color) → out_color
table — the actual colors in the data, no boolean projection. Mirrors
b1948b0a's `mapping: set[tuple[Color, Color]]` with one extra input arity.
The XOR pattern of this task is implicit in the table's rows.

== Notes ==

- First-draft layout: raw 4-tuple destructure to read input distances and
  rebuild output positions against the new bound. Body avoids Dir /
  DiagDir literals that would bake orientation into the rule.
- 2-input mapping shape: `set[tuple[Color, Color, Color]]`. Sibling
  5d2a5c43 uses the same body, different mapping (OR fold).
- Output positions align by Position equality across `left` and `right`,
  so the pair join is `p == p2` (Souffle: shared variable).
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    half_w: int
    mapping: set[tuple[Color, Color, Color]]


CONSTS = Consts(
    half_w=4,
    mapping={
        (C0, C0, C0),  # both empty → C0
        (C0, C5, C2),  # right only → C2
        (C8, C0, C2),  # left only → C2
        (C8, C5, C0),  # both filled → C0
    },
)


def solve(grid: Grid, c: Consts) -> Grid:
    half = c.half_w

    # Left half: input cells within `half` of one edge; output position
    # rebuilt against the smaller bound along that axis.
    left = {
        ((t, b, l, half - 1 - l), col)
        for ((t, b, l, _), col) in grid
        if l < half
    }

    # Right half: cells within `half` of the opposite edge; output
    # position rebuilt symmetrically so it aligns with `left` by Position.
    right = {
        ((t, b, half - 1 - r, r), col)
        for ((t, b, _, r), col) in grid
        if r < half
    }

    # out(p, t) :- left(p, l), right(p, r), mapping(l, r, t).
    return {
        (p, t)
        for (p, l_col) in left
        for (p2, r_col) in right
        if p == p2
        for (lk, rk, t) in c.mapping
        if l_col == lk and r_col == rk
    }
