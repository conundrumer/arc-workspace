"""Solver for ARC task e9afcf9a — cell permutation via labeled grids.

Rule (Souffle form):
    out(p_out, col) :- in(p_in, col), mapping(p_in, p_out).

Same body as ca8de6ea (canonical Position-keyed-substitution shape).
The mapping is a 1-to-1 cell permutation: at odd columns, rows 0 and 1
swap; even columns are unchanged. Output dims = input dims (2×6 fixed
across train+test).

== Notes ==

- Conceptual rule is "stripe → checkerboard" — input has two uniform
  horizontal stripes, output is a 2-color checkerboard from those
  colors. Under the uniform-rows precondition, that rule reduces to
  the position permutation declared here. (For non-uniform inputs the
  TS reference reads only `input[0][0]` and `input[1][0]` — strict
  position-permutation semantics would not match.)
- The labeled-grid declaration makes the swap-at-odd-columns pattern
  legible at a glance vs an enumerated list of 12 (Position, Position)
  pairs.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    mapping: set[tuple[Position, Position]]


CONSTS = Consts(
    mapping=position_mapping(
        input_rows=[
            [1, 2,  3,  4,  5,  6],
            [7, 8,  9, 10, 11, 12],
        ],
        output_rows=[
            [1, 8,  3, 10,  5, 12],
            [7, 2,  9,  4, 11,  6],
        ],
    ),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(p_out, col) :- in(p_in, col), mapping(p_in, p_out).
    return {
        (p_out, col)
        for (p_in, col) in grid
        for (m_in, p_out) in c.mapping
        if p_in == m_in
    }
