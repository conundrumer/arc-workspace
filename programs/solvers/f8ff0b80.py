"""Output a column of non-bg colors ordered by descending count in the input."""

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
    # TODO: get height via set size not max
    max_r = max(r for (_, r) in ranks)
    # out(P, col) :- rank(col, R), span(VERTICAL, max_r+1, P), dist(P, TOP) = R.
    return {(p, col)
            for (col, r) in ranks
            for p in span(Axis.VERTICAL, max_r + 1) if dist(p, Dir.TOP) == r}
