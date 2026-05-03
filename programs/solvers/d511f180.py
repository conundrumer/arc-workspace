"""Solver for ARC task d511f180 — color swap; same rule as b1948b0a.

Mapping: `{(C5, C8), (C8, C5)}` — bidirectional 2-fact relation. Color swap
is just substitution-as-rule-pattern with both directions in the relation;
no special-casing needed.

See b1948b0a.py for the rule (Souffle + Python forms).
"""

from dataclasses import dataclass

from programs.lib import Color, Grid


@dataclass(frozen=True)
class Consts:
    mapping: set[tuple[Color, Color]]


CONSTS = Consts(mapping={(Color.C5, Color.C8), (Color.C8, Color.C5)})


def solve(grid: Grid, c: Consts) -> Grid:
    # mapping_keys(x) :- mapping(x, _).
    mapping_keys = {f for (f, _) in c.mapping}

    # out(p, t) :- in(p, x), mapping(x, t).
    mapped = {(p, t) for (p, col) in grid for (f, t) in c.mapping if col == f}

    # out(p, x) :- in(p, x), !mapping_keys(x).
    unmapped = {(p, col) for (p, col) in grid if col not in mapping_keys}

    return mapped | unmapped
