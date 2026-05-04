"""Input is N identical tiles; output is the tile.

Placeholders:
- position-destructure: component-wise modulo on raw Position for symmetric N-fold collapse along both axes.

Rule (Souffle form):
    out(t mod inner_h, r mod inner_w, b mod inner_h, l mod inner_w, col)
        :- in(t, r, b, l, col).

Each input cell projects to its canonical in-tile position via component-
wise modulo against the inner dims. The N redundant copies (one per tile
position) collide on the same (canonical_p, col) tuple; set semantics
keeps one (Pattern: set dedup as semantics).

== Notes ==

- Symmetric collapse: all N tiles are IDENTITY copies of one inner. No
  per-tile transform involved — uniform N-fold replication being inverted.
- Modulo arithmetic does the inverse-of-combine from `tile_d4`. With the
  layout primitive cluster lifted, the body collapses to one call against
  a symmetric primitive parameterized by axis and N.
- Consts: `template: D4Template` for symmetry with `tile_d4` solvers.
  The template's dims drive output dims; d4 values are uniformly IDENTITY.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    template: D4Template


CONSTS = Consts(
    template=d4_template_from_rows([[D4.IDENTITY, D4.IDENTITY, D4.IDENTITY]])
)


def solve(grid: Grid, c: Consts) -> Grid:
    # Template dims.
    (mt0, mr0, mb0, ml0), _ = next(iter(c.template))
    template_h = mt0 + mb0 + 1
    template_w = ml0 + mr0 + 1

    # Input dims.
    (t0, r0, b0, l0), _ = next(iter(grid))
    full_h = t0 + b0 + 1
    full_w = l0 + r0 + 1

    # Inner (output) dims.
    inner_h = full_h // template_h
    inner_w = full_w // template_w

    # out((t mod inner_h, r mod inner_w, b mod inner_h, l mod inner_w), col)
    #     :- in((t, r, b, l), col).
    return {
        ((t % inner_h, r % inner_w, b % inner_h, l % inner_w), col)
        for ((t, r, b, l), col) in grid
    }
