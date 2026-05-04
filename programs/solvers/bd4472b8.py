"""Header section preserved, body section cycles header.

Placeholders:
- position-destructure: section split (`t < c.body_start`), grid width, and cyclic source-col index (`(t - body_start) % W`). Conceptual primitives are non-uniform-section-split (header/body sections with different roles) plus anchored cyclic tile (same family as ba26e723's stride).

Rule (informal):
    The grid splits into two sections along the top axis: a header section
    (rows 0..body_start-1, plays the source role — first row supplies
    body colors, second row is a divider passed through unchanged) and
    a body section (rows body_start..end). Each body row is filled
    uniformly with header[(row_offset) mod W], where row_offset is the
    row's distance below the header section and W is the grid width.

== Notes ==

- The const `body_start` is *not* a primitive — just the integer offset
  where the body section begins. Conceptual primitive is "section split,"
  with the integer derived from section sizes.
- Body fill is per-row uniform: each body cell's color depends only on
  its row, not its column. The header→body cyclic mapping does the work;
  per-cell propagation just spreads the row color.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    body_start: int


CONSTS = Consts(body_start=2)


def solve(grid: Grid, c: Consts) -> Grid:
    # Grid width via raw destructure.
    (_, r0, _, l0), _ = next(iter(grid))
    W = l0 + r0 + 1

    # header_by_col(l, color) :- in((0, _, _, l), color).
    header_by_col = {(l, col) for ((t, _, _, l), col) in grid if t == 0}

    # header_section(p, col) :- in(p, col), p.t < c.body_start.
    header_section = {
        ((t, r, b, l), col)
        for ((t, r, b, l), col) in grid
        if t < c.body_start
    }

    # body_section(p, color) :- in(p, _), p.t >= c.body_start,
    #                           header_by_col((p.t - c.body_start) mod W, color).
    body_section = {
        ((t, r, b, l), color)
        for ((t, r, b, l), _) in grid
        if t >= c.body_start
        for (h_l, color) in header_by_col
        if h_l == (t - c.body_start) % W
    }

    return header_section | body_section
