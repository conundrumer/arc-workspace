"""Each marker drops to the fall-direction edge of its perpendicular slice; original positions clear to background."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    marker: Color
    bg: Color
    fall_to: Dir


CONSTS = Consts(marker=C1, bg=C0, fall_to=Dir.BOTTOM)


def solve(grid: Grid, c: Consts) -> Grid:
    # marker_lines(s) :- in(p, c.marker), s = across-slice(p, axis_of(c.fall_to)).
    marker_lines = {split(p, axis_of(c.fall_to)).across for (p, col) in grid if col == c.marker}
    # cleared(p, c.bg) :- in(p, c.marker).
    cleared = {(p, c.bg) for (p, col) in grid if col == c.marker}
    # landed(p, c.marker) :- in(p, _), dist(p, c.fall_to) = 0, marker_lines(across-slice(p, ...)).
    landed = {(p, c.marker) for (p, _) in grid
              if dist(p, c.fall_to) == 0
              and split(p, axis_of(c.fall_to)).across in marker_lines}
    # passthrough(p, col) :- in(p, col), !changed(p).
    changed = {p for (p, _) in cleared | landed}
    passthrough = {(p, col) for (p, col) in grid if p not in changed}
    return cleared | landed | passthrough
