"""Recolor a binary input: bg cells take a fill color derived from the input's fg via a fixed mapping; fg cells become bg."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    bg: Color
    recolor: frozenset[tuple[Color, Color]]


CONSTS = Consts(
    bg=C0,
    recolor=frozenset({
        (C3, C1),
        (C5, C4),
        (C8, C2),
    }),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # fg(col) :- in(_, col), col != c.bg.
    (fg,) = {col for (_, col) in grid if col != c.bg}
    # fill(out) :- fg(col), recolor(col, out).
    (fill,) = {out for (a, out) in c.recolor if a == fg}
    # out(p, fill) :- in(p, c.bg).
    on = {(p, fill) for (p, col) in grid if col == c.bg}
    # out(p, c.bg) :- in(p, col), col != c.bg.
    off = {(p, c.bg) for (p, col) in grid if col != c.bg}
    return on | off
