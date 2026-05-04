"""Solver for ARC task e345f17b — fold halves via color mapping (no margin).

Status: placeholder — same body as 34b99a2b (canonical for this shape).
        Layout split is raw Position destructure; layout primitive
        cluster pending.

Rule form, two-form documentation, and layout notes: see
`programs/solvers/34b99a2b.py`.

Difference from 34b99a2b: input width = 2 * half_w (no divider column).
The `l < half` / `r < half` inequalities partition cleanly without a
margin to discard. Mapping is NOR-shaped: output is C4 iff both halves
are C0; otherwise C0.

== Notes ==

- 2-input mapping shape: `set[tuple[Color, Color, Color]]`. Sibling
  34b99a2b uses the same body, different mapping (XOR fold);
  5d2a5c43 uses it too (OR fold).
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
        (C0, C0, C4),
        (C0, C5, C0),
        (C6, C0, C0),
        (C6, C5, C0),
    },
)


def solve(grid: Grid, c: Consts) -> Grid:
    half = c.half_w

    # Left half: input cells within `half` of one edge; output position
    # rebuilt against the smaller bound along that axis.
    left = {
        ((t, half - 1 - l, b, l), col)
        for ((t, _, b, l), col) in grid
        if l < half
    }

    # Right half: cells within `half` of the opposite edge; output
    # position rebuilt symmetrically so it aligns with `left` by Position.
    right = {
        ((t, r, b, half - 1 - r), col)
        for ((t, r, b, _), col) in grid
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
