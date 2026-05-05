"""Solver for ARC task a85d4709 — fill each row by row-template lookup.

Rule (Souffle form):
    row_cell(Ac, Al, Co) :- in(P, Co), split(P, c.axis) = (Al, Ac).
    row_color(Ac, OutC)  :- mapping(K, OutC),
                            set_eq(row_cell(Ac, _, _), color_grid(K, _, _)).
    out(P, OutC)         :- in(P, _), split(P, c.axis) = (_, Ac),
                            row_color(Ac, OutC).

Datalog-lite (Python) form, with the host materializing the boxed row:
    acrosses(Ac)         :- row_cell(Ac, _, _).
    row_box(Ac, K)       :- acrosses(Ac), K = frozenset{ (Al, Co) : row_cell(Ac, Al, Co) }.
    row_color(Ac, OutC)  :- row_box(Ac, K), mapping(K, OutC).

Two-form: Souffle's `set_eq` is the count-trick (intersection size matches
both side sizes); the host's frozenset `==` collapses it into one
operator, so an extra `row_box` rule materializes per-row frozensets
host-side.

Output dims = input dims; only colors change.

== Notes ==

- Mapping shape: `set[tuple[frozenset[tuple[Position, Color]], Color]]` —
  shape-keyed (Patterns: shape-keyed mapping). The whole row is the key,
  not a projection of one cell within it. A "marker position" derivation
  would discard the rest of the row's content; the row-template carries
  it. (Object Principle 9 — stay close to ARC reality.)

- Three mapping entries cover the three rows possible in a 3-wide grid.
  Full coverage; no fallback. A variant with unmapped rows would add a
  default branch.

- Axis lives in Consts (HORIZONTAL). A rotated variant swaps the const,
  not the body (Object Principle 6).
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    axis: Axis
    mapping: set[tuple[frozenset[tuple[Position, Color]], Color]]


CONSTS = Consts(
    axis=Axis.HORIZONTAL,
    mapping={
        (color_grid([[5, 0, 0]]), C2),  # marker at left
        (color_grid([[0, 5, 0]]), C4),  # marker at middle
        (color_grid([[0, 0, 5]]), C3),  # marker at right
    },
)


def solve(grid: Grid, c: Consts) -> Grid:
    # row_cell(Ac, Al, Co) :- in(P, Co), split(P, c.axis) = (Al, Ac).
    row_cell = {(ac, al, col) for (p, col) in grid for (al, ac) in [split(p, c.axis)]}

    # acrosses(Ac) :- row_cell(Ac, _, _).
    acrosses = {ac for (ac, _, _) in row_cell}

    # row_box(Ac, K) :- acrosses(Ac), K = frozenset{ (Al, Co) : row_cell(Ac, Al, Co) }.
    # (Host materialization for set_eq — see docs Souffle alignment.)
    row_box = {
        (ac, frozenset((al, co) for (ac2, al, co) in row_cell if ac2 == ac))
        for ac in acrosses
    }

    # row_color(Ac, OutC) :- row_box(Ac, K), mapping(K, OutC).
    row_color = {(ac, oc) for (ac, k) in row_box for (k2, oc) in c.mapping if k2 == k}

    # out(P, OutC) :- in(P, _), split(P, c.axis) = (_, Ac), row_color(Ac, OutC).
    return {
        (p, oc)
        for (p, _) in grid
        for (ac2, oc) in row_color
        if ac2 == split(p, c.axis).across
    }
