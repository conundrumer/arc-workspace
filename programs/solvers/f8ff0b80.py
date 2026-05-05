"""Output a column of non-bg colors ordered by descending count in the input.

Placeholders:
- position-construction: column anchored at Dir.TOP, width 1, indexed by rank — built as raw 4-distance tuple.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    bg: Color


CONSTS = Consts(bg=C0)


def solve(grid: Grid, c: Consts) -> Grid:
    # count(col, n) :- col != c.bg, n = count : { in(_, col) }.
    counts = {(col, sum(1 for (_, col2) in grid if col2 == col))
              for (_, col) in grid if col != c.bg}
    # rank(col, r) :- count(col, n), r = count : { count(_, n'), n' > n }.
    ranks = {(col, sum(1 for (_, n2) in counts if n2 > n))
             for (col, n) in counts}
    # max_r :- max : { rank(_, R) }.
    max_r = max(r for (_, r) in ranks)
    # out((R, 0, max_r-R, 0), col) :- rank(col, R).
    return {((r, 0, max_r - r, 0), col) for (col, r) in ranks}
