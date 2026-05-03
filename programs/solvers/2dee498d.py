"""Solver for ARC task 2dee498d — input is N identical tiles; output is the tile.

Status: placeholder — raw Position destructure (no `untile_d4` primitive yet;
see docs/solvers.md).

Conceptual rule: input == tile_d4(c.template, output). This solver inverts.

Rule (Souffle form, valid for templates where every cell is IDENTITY):
    out(t mod inner_h, r mod inner_w, b mod inner_h, l mod inner_w, col)
        :- in(t, r, b, l, col).

Each input cell projects to its position-within-the-tile via component-wise
modulo against the inner dims. The N redundant copies (one per tile cell)
collide on the same (small_p, col) tuple; set semantics keeps one (Pattern:
set dedup as semantics).

== Notes ==

- Modulo arithmetic is the inverse-of-combine from `tile_d4`. When
  `untile_d4` lands as a primitive, the body collapses to one call.

- Generalization to non-IDENTITY templates needs per-tile inverse-d4
  application before mod'ing.

- Consts: `template: D4Template` for symmetry with `tile_d4` solvers.
  The template's dims drive output dims; d4 values are unused under the
  IDENTITY-only assumption.
"""

from dataclasses import dataclass

from programs.lib import D4, D4Template, Grid, d4_template_from_rows


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
