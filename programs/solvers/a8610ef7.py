"""Solver for ARC task a8610ef7 — recolor each non-bg cell by FLIP_TB pair existence.

Rule (Souffle form):
    out(p, c.bg)        :- in(p, c.bg).
    out(p, c.matched)   :- in(p, x),                      x != c.bg,
                           in(apply(c.mirror, p), y),     y != c.bg.
    out(p, c.unmatched) :- in(p, x),                      x != c.bg,
                           in(apply(c.mirror, p), c.bg).

Read: every cell partitions into three disjoint buckets — bg passes
through, non-bg cells are recolored by whether their mirror (under
c.mirror, here FLIP_TB) is also non-bg. Mirror non-bg → matched
(paired); mirror bg → unmatched (orphan).

Datalog-lite Python form: host materializes a `non_bg` projection
(`p :- in(p, x), x != c.bg`) for O(1) membership tests. The projection
is one extra rule that collapses on Souffle port — the matched /
unmatched bodies inline the disjunction directly.

== Notes ==

- Consts: `mirror: D4` (the symmetry under which pairing is checked,
  D4 in Consts per Object Principle 6); `bg`, `matched`, `unmatched`:
  Color (opaque, equality only).
- Three-bucket `matched | unmatched | bg` — generalization of the
  two-bucket pattern in c7d4e6ad. Buckets are disjoint and cover the
  grid; output is set-union.
- A rotated variant (left-right mirror, etc.) swaps `mirror`; body
  unchanged.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    mirror: D4
    bg: Color
    matched: Color
    unmatched: Color


CONSTS = Consts(mirror=D4.FLIP_TB, bg=C0, matched=C2, unmatched=C5)


def solve(grid: Grid, c: Consts) -> Grid:
    # non_bg(p) :- in(p, x), x != c.bg.
    non_bg = {p for (p, col) in grid if col != c.bg}

    # bg_out(p, c.bg) :- in(p, c.bg).
    bg_out = {(p, c.bg) for (p, col) in grid if col == c.bg}

    # matched(p, c.matched) :- non_bg(p), non_bg(apply(c.mirror, p)).
    matched = {(p, c.matched) for p in non_bg if apply(c.mirror, p) in non_bg}

    # unmatched(p, c.unmatched) :- non_bg(p), !non_bg(apply(c.mirror, p)).
    unmatched = {(p, c.unmatched) for p in non_bg if apply(c.mirror, p) not in non_bg}

    return bg_out | matched | unmatched
