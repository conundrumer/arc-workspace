"""Classify the input by invariance under a fixed set of d4 symmetries."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    syms: frozenset[D4]
    sym_out: frozenset[tuple[Position, Color]]
    asym_out: frozenset[tuple[Position, Color]]


CONSTS = Consts(
    syms=frozenset({D4.FLIP_LR, D4.FLIP_TB}),
    sym_out=color_grid([[1]]),
    asym_out=color_grid([[7]]),
)


def solve(grid: Grid, c: Consts) -> Grid:
    # non_invariant(d) :- d in c.syms, {(apply(d,p), col) : in(p, col)} != grid.
    non_invariant = {d for d in c.syms if {(apply(d, p), col) for (p, col) in grid} != grid}
    # is_sym :- !non_invariant(_).
    is_sym = not non_invariant
    # out(p, col) :- is_sym, sym_out(p, col).
    r1 = {(p, col) for (p, col) in c.sym_out if is_sym}
    # out(p, col) :- !is_sym, asym_out(p, col).
    r2 = {(p, col) for (p, col) in c.asym_out if not is_sym}
    return r1 | r2
