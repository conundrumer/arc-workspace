"""Recolor a binary input: marker positions take the input's main color; the main color elsewhere becomes background."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    marker: Color
    bg: Color


CONSTS = Consts(marker=C5, bg=C0)


def solve(grid: Grid, c: Consts) -> Grid:
    # main(col) :- in(_, col), col != c.marker.
    (main,) = {col for (_, col) in grid if col != c.marker}
    # out(p, main) :- in(p, c.marker).
    on = {(p, main) for (p, col) in grid if col == c.marker}
    # out(p, c.bg) :- in(p, col), col != c.marker.
    off = {(p, c.bg) for (p, col) in grid if col != c.marker}
    return on | off
