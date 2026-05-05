"""Apply a fixed position permutation."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    perm: frozenset[tuple[Position, Position]]


CONSTS = Consts(
    perm=frozenset(position_mapping(
        [[1], [2], [3], [4], [5]],
        [[2], [1], [3], [5], [4]],
    )),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(p_out, col) :- in(p_in, col), perm(p_in, p_out).
    return {(p_out, col) for (p_in, col) in grid for (a, p_out) in c.perm if a == p_in}
