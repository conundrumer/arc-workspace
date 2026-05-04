"""Recolor C4→C6 on every 3rd column from LEFT.

Placeholders:
- arithmetic-predicate: `dist(p, c.anchor) % c.stride == 0` stride predicate. Lives in the layout concept cluster alongside anchored tiling and corner anchoring; defer the primitive until the cluster's shape clarifies.

Rule (Souffle form — canonical):
    striped(p) :- in(p, _), dist(p, c.anchor) mod c.stride == 0.
    out(p, t) :- in(p, x), mapping(x, t), striped(p).
    out(p, x) :- in(p, x), !(mapping(x, _) && striped(p)).

Datalog-lite (Python) form, with the projection forced by the host:
    striped(p)      :- in(p, _), dist(p, c.anchor) mod c.stride == 0.
    mapping_keys(x) :- mapping(x, _).
    out(p, t)       :- in(p, x), mapping(x, t), striped(p).
    out(p, x)       :- in(p, x), !(mapping_keys(x) && striped(p)).

Generalization of b1948b0a: substitution gated by a positional predicate
(`striped`) instead of applying unconditionally.

== Notes ==

- Consts: `mapping: set[tuple[Color, Color]]` (single-row relation here),
  `anchor: Dir = LEFT`, `stride: int = 3`. Mapping shape unchanged from
  b1948b0a; anchor + stride are new.
- The `striped` predicate is `dist(p, c.anchor) mod c.stride == 0` — Dir-
  parameterized so a top-anchored or right-anchored variant swaps the const,
  not the body.
- The `%` arithmetic is conceptually adjacent to anchored tiling
  (D4Template at stride) and corner-anchored crop (single-position version
  of the same anchor idea). Awaiting more layout data points before factoring.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    mapping: set[tuple[Color, Color]]
    anchor: Dir
    stride: int


CONSTS = Consts(
    mapping={(C4, C6)},
    anchor=Dir.LEFT,
    stride=3,
)


def solve(grid: Grid, c: Consts) -> Grid:
    # striped(p) :- in(p, _), dist(p, c.anchor) mod c.stride == 0.
    striped = {p for (p, _) in grid if dist(p, c.anchor) % c.stride == 0}

    # mapping_keys(x) :- mapping(x, _).
    mapping_keys = {f for (f, _) in c.mapping}

    # out(p, t) :- in(p, x), mapping(x, t), striped(p).
    mapped = {
        (p, t)
        for (p, col) in grid
        for (f, t) in c.mapping
        if col == f and p in striped
    }

    # out(p, x) :- in(p, x), !(mapping_keys(x) && striped(p)).
    unmapped = {
        (p, col)
        for (p, col) in grid
        if not (col in mapping_keys and p in striped)
    }

    return mapped | unmapped
