"""Solver for ARC task d10ecb37 — crop to top-left 2×2.

Status: placeholder — raw Position destructure (no `crop` primitive; the
crop family is too varied to factor yet, see docs/solvers.md).

Rule (Souffle form):
    out(t, w-1-l, h-1-t, l, c) :- in(t, r, b, l, c), t < h, l < w.

The output is built from cells in the TL corner of the input. Discarded
distances (r, b in the input) are recomputed against the smaller output
bounds.

== Notes ==

- Consts: `h` and `w`. TL anchor is hardcoded in the body; an anchor pair
  joins consts when a `crop` primitive lands.

- Output dims differ from input — output is smaller (Pattern:
  output-dimension classes / scaled-down).
"""

from dataclasses import dataclass

from programs.lib import Grid


@dataclass(frozen=True)
class Consts:
    h: int
    w: int


CONSTS = Consts(h=2, w=2)


def solve(grid: Grid, c: Consts) -> Grid:
    # out((t, w-1-l, h-1-t, l), col) :- in((t, _, _, l), col), t < h, l < w.
    return {
        ((t, c.w - 1 - l, c.h - 1 - t, l), col)
        for ((t, _, _, l), col) in grid
        if t < c.h and l < c.w
    }
