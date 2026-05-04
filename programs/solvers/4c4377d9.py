"""Solver for ARC task 4c4377d9 — stack vertically-flipped input above input.

Rule (Souffle form):
    out :- tile_d4(c.template, in).

Output dims = (2 * input_h, input_w). Top half is the input vertically
flipped; bottom half is the input. `tile_d4` with the 2×1 template
[[FLIP_TB], [IDENTITY]] places the flipped copy at meta-row 0 and the
original at meta-row 1.

== Notes ==

- Same body shape as 6d0aefbc / 59341089 / c9e6f938 — all single
  `tile_d4` calls; only the template differs.

- Template encodes the orientation choice per meta-cell. A sibling task
  with the original on top and the flip below would swap the template
  rows; horizontal-mirror variant would use FLIP_LR. Object Principle 6
  in practice — orientation is a value.

- FLIP_TB preserves input dims (it's an index permutation across the
  vertical axis), so `tile_d4`'s square-or-axis-preserving precondition
  holds for any input rectangle.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    template: D4Template


CONSTS = Consts(
    template=d4_template_from_rows([
        [D4.FLIP_TB],
        [D4.IDENTITY],
    ]),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # out :- tile_d4(c.template, in).
    return tile_d4(c.template, grid)
