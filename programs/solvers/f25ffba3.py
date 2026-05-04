"""Solver for ARC task f25ffba3 — stamp bottom half of input with D4 set.

Status: placeholder — raw arithmetic on bottom-distance for the half
        partition. Rule wants an edge-anchored half-extract; corner_view
        is the wrong shape (see incidents_7e4d4f7c.md).

Rule (Souffle form):
    out(apply(D, P), col) :- in(P, col),
                             dist(P, c.data_dir) < c.half_h,
                             stamps(D).

Each input cell whose distance to c.data_dir is less than c.half_h
("data half") gets stamped at every D4 in c.stamps. IDENTITY keeps the
data in place; FLIP_TB places a vertically-flipped copy in the empty
half.

== Notes ==

- Sibling of be03b35f: same multi-D4 stamp shape, but here the source
  region is an edge-anchored half, not a corner-anchored quadrant.

- Distinct from 4c4377d9: that solver tile_d4'd the entire input as
  inner; here only half the input carries data, and stamping does the
  fill without an explicit extract step.

- c.data_dir is the edge the data is anchored to. c.stamps's D4s must
  be axis-compatible with c.data_dir; FLIP_TB matches BOTTOM/TOP
  (vertical axis). A sibling task with data on the RIGHT half would
  swap data_dir=RIGHT and stamps={IDENTITY, FLIP_LR}.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    data_dir: Dir
    half_h: int
    stamps: set[D4]


CONSTS = Consts(
    data_dir=Dir.BOTTOM,
    half_h=5,
    stamps={D4.IDENTITY, D4.FLIP_TB},
)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(apply(D, P), col) :- in(P, col), dist(P, c.data_dir) < c.half_h, stamps(D).
    return {
        (apply(d, p), col)
        for (p, col) in grid
        if dist(p, c.data_dir) < c.half_h
        for d in c.stamps
    }
