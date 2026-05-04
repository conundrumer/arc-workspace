"""Solver for ARC task c8f0f002 — color substitution; same rule as b1948b0a.

Mapping: `{(C7, C5)}`.

See b1948b0a.py for the rule (Souffle + Python forms) and notes on
substitution-as-rule-pattern.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    mapping: set[tuple[Color, Color]]


CONSTS = Consts(mapping={(C7, C5)})


def solve(grid: Grid, c: Consts) -> Grid:
    # mapping_keys(x) :- mapping(x, _).
    mapping_keys = {f for (f, _) in c.mapping}

    # out(p, t) :- in(p, x), mapping(x, t).
    mapped = {(p, t) for (p, col) in grid for (f, t) in c.mapping if col == f}

    # out(p, x) :- in(p, x), !mapping_keys(x).
    unmapped = {(p, col) for (p, col) in grid if col not in mapping_keys}

    return mapped | unmapped
