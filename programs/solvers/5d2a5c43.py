"""Fold halves about a divider via color mapping.

Placeholders:
- position-destructure: layout split. Same cluster as 34b99a2b (uniform split-in-halves with margin); only `mapping` differs (OR fold vs XOR fold — same body shape).

Rule (Souffle form):
    left(p, c)  :- in(p, c), within `c.half_w` of one edge, repositioned.
    right(p, c) :- in(p, c), within `c.half_w` of the opposite edge,
                   repositioned to align with `left` by Position.
    out(p, t) :- left(p, l), right(p, r), mapping(l, r, t).

The `mapping` relation enumerates (left_color, right_color) → out_color.
OR fold here: any cell C4 → C8, neither → C0.

== Notes ==

- Sibling of 34b99a2b: same body, different `mapping`. Two witnesses of
  the layout-split-with-margin + 2-input color fold pattern.
- First-draft layout: raw 4-tuple destructure. Body avoids Dir / DiagDir
  literals.
- Mapping is `set[tuple[Color, Color, Color]]` — mirrors b1948b0a's
  `mapping: set[tuple[Color, Color]]` with one extra input arity.
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
        (C0, C0, C0),  # neither filled → C0
        (C0, C4, C8),  # right only → C8
        (C4, C0, C8),  # left only → C8
        (C4, C4, C8),  # both filled → C8
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
