"""Recolor rows by uniformity (uniform→C5, else→C0).

Placeholders:
- pair-existence-count: pair-existence trick for "more than one distinct color in a group". Special case of a count aggregator (Souffle: `n = count : { body }`, filter `n > 1`). Lift to a `count_per` (or equivalent) primitive when a task forces general count semantics (==N, >K with K≥2, or filtering on the count value itself).

Rule (Souffle form):
    non_uniform(across) :- in(p1, x1), in(p2, x2),
                           split(p1, c.axis) = (_, across),
                           split(p2, c.axis) = (_, across),
                           x1 != x2.
    out(p, c.uniform_color)     :- in(p, _),
                                   split(p, c.axis) = (_, across),
                                   !non_uniform(across).
    out(p, c.non_uniform_color) :- in(p, _),
                                   split(p, c.axis) = (_, across),
                                   non_uniform(across).

The derived `non_uniform(across)` relation is "groups along c.axis containing
at least two distinct colors." Same shared-across-binding idiom as c7d4e6ad
— two `split()` calls share the across-component to scope a join to
"same row" (axis=HORIZONTAL) or "same column" (axis=VERTICAL).

== Notes ==

- Consts: `axis: Axis` (the axis along which uniformity is checked) plus
  two output colors keyed by the boolean predicate. A column-wise variant
  reuses this body verbatim with axis=VERTICAL.
- Output color isn't a substitution — every cell is overwritten regardless
  of its input color. The discriminator is row/column-level structure.
- Self-join on `grid` for the derived relation. O(n²) over cells; fine at
  ARC sizes.
- The two-color "boolean output mapping" feels like it could generalize
  (boolean predicate → color via 2-row mapping) but only if a second task
  with the same shape lands. Two separate Color fields for now.
- Pair-existence (`exists p1, p2 in same group with c1 != c2`) is the
  count-free encoding for >1. The general count form would project
  (across, color), then count : { ... } per across, then filter — three
  rules vs one. Cheap to swap when count_per lifts.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    axis: Axis
    uniform_color: Color
    non_uniform_color: Color


CONSTS = Consts(
    axis=Axis.HORIZONTAL,
    uniform_color=C5,
    non_uniform_color=C0,
)


def solve(grid: Grid, c: Consts) -> Grid:
    # non_uniform(across) :- in(p1, x1), in(p2, x2),
    #                       split(p1, c.axis) = (_, across1),
    #                       split(p2, c.axis) = (_, across2),
    #                       across1 == across2, x1 != x2.
    non_uniform = {
        across1
        for (p1, x1) in grid
        for (p2, x2) in grid
        for across1 in [split(p1, c.axis).across]
        for across2 in [split(p2, c.axis).across]
        if across1 == across2 and x1 != x2
    }

    # out(p, c.non_uniform_color) :- in(p, _), split(p, c.axis) = (_, across), non_uniform(across).
    nonuniform = {
        (p, c.non_uniform_color)
        for (p, _) in grid
        if split(p, c.axis).across in non_uniform
    }

    # out(p, c.uniform_color) :- in(p, _), split(p, c.axis) = (_, across), !non_uniform(across).
    uniform = {
        (p, c.uniform_color)
        for (p, _) in grid
        if split(p, c.axis).across not in non_uniform
    }

    return uniform | nonuniform
