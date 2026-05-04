"""Solver for ARC task b1948b0a — color substitution via a mapping relation.

Rule (Souffle form — canonical):
    out(p, y) :- in(p, x), mapping(x, y).
    out(p, x) :- in(p, x), !mapping(x, _).

Datalog-lite (Python) form, with the projection forced by the host:
    mapping_keys(x) :- mapping(x, _).
    out(p, y)       :- in(p, x), mapping(x, y).
    out(p, x)       :- in(p, x), !mapping_keys(x).

Two-form: the Souffle version's `!mapping(x, _)` is existential negation
with anonymous variable; Python set comprehensions can't do that, so the
projection `mapping_keys` is materialized as an extra rule. The projection
collapses on a Souffle port.

== Notes ==

- Consts: `mapping: set[tuple[Color, Color]]` — a relation, not a dict.
  Single-substitution case is a one-element relation; same shape generalizes
  to multi-row or cross-entity substitution.

- The body writes the rule pattern directly — no `recolor`-shaped helper.
  Substitution is a rule pattern, not a primitive function (see
  docs/solvers.md, Object Principle 7 and Souffle alignment).
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    mapping: set[tuple[Color, Color]]


CONSTS = Consts(mapping={(C6, C2)})


def solve(grid: Grid, c: Consts) -> Grid:
    # mapping_keys(x) :- mapping(x, _).
    mapping_keys = {f for (f, _) in c.mapping}

    # out(p, t) :- in(p, x), mapping(x, t).
    mapped = {(p, t) for (p, col) in grid for (f, t) in c.mapping if col == f}

    # out(p, x) :- in(p, x), !mapping_keys(x).
    unmapped = {(p, col) for (p, col) in grid if col not in mapping_keys}

    return mapped | unmapped
