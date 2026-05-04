"""Solver for ARC task ca8de6ea — collapse 5×5 X-pattern to dense 3×3.

Status: placeholder — hand-built Position remap table (9 entries),
        declared via `position_mapping` (labeled grids whose matching
        labels identify the pairs).

Rule (Souffle form):
    out(P_out, col) :- in(P_in, col), mapping(P_in, P_out).

Output dims: (3, 3). Each of the 9 non-bg input cells maps to a unique
output cell; bg cells (the 16 zeros around the X) drop out because they
don't match any mapping key.

== Notes ==

- Mapping shape: `set[tuple[Position, Position]]` — input position to
  output position. Substitution-on-Position mirrors b1948b0a's
  substitution-on-Color (Object Principle 7). Pure rule pattern, no
  helper function.

- The mapping is declared via `position_mapping(input_rows, output_rows)`
  — two labeled grids; matching non-zero labels identify the position
  pairs. The visual layout of the labeled grids makes the rule's
  spatial structure (which input cell goes to which output cell)
  legible at a glance, vs 9 hand-rolled 4-tuple pairs.

- Structural observation: the 9 input non-bg cells form three rings
  around the center — 4 outer corners (distance 0 from two edges), 4
  inner corners (distance 1 from two edges), 1 center. Walking the
  input cells CW from outer-TL gives outer-TL, inner-TL, outer-TR,
  inner-TR, outer-BR, inner-BR, outer-BL, inner-BL, center. The output
  3×3 cells in matching CW order (TL, top, TR, right, BR, bottom, BL,
  left, center) are paired by ring-spiral position. Whether this
  generalizes to a primitive depends on a second occurrence; no
  candidate proposed without a worked-out shape.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    mapping: set[tuple[Position, Position]]


CONSTS = Consts(
    mapping=position_mapping(
        input_rows=[
            [1, 0, 0, 0, 3],
            [0, 2, 0, 4, 0],
            [0, 0, 9, 0, 0],
            [0, 8, 0, 6, 0],
            [7, 0, 0, 0, 5],
        ],
        output_rows=[
            [1, 2, 3],
            [8, 9, 4],
            [7, 6, 5],
        ],
    ),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(P_out, col) :- in(P_in, col), mapping(P_in, P_out).
    return {
        (p_out, col)
        for (p_in, col) in grid
        for (m_in, p_out) in c.mapping
        if p_in == m_in
    }
