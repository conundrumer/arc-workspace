"""D4 transform on the 2×2 block-grid.

Placeholders:
- position-destructure: block-level D4. Conceptual primitive is "apply D4 at block granularity": coarsen Position to its block, apply D4 in block-grid coords, recombine with the per-block local. `untile_d4`-then-retile would absorb this.

Rule (Souffle form):
    out((bt*K + t%K, br*K + r%K, bb*K + b%K, bl*K + l%K), col)
        :- in((t, r, b, l), col),
           apply(c.block_d4, (t/K, r/K, b/K, l/K)) = (bt, br, bb, bl).
    where K = c.block_size.

Read: coarsen each Position to its K×K block, apply a D4 to the block-
grid coords, then recombine with the per-block local position. Per-block
content is preserved — the inner is not transformed.

== Notes ==

- Multiple applicable D4s. Every observed example has diagonal-symmetric
  block placements with identical inner glyphs; FLIP_TB and FLIP_LR both
  reproduce all outputs. ROT_180 / FLIP_DIAG / FLIP_ANTIDIAG fix the
  diagonal pattern so they fail. CONSTS picks FLIP_TB; FLIP_LR is an
  equally valid alt the materialized data doesn't distinguish.
  (Rule alts under `kind="rule"` are deferred.)
- Block dim is square in this task — `block_size` covers both axes.
  Non-square blocks would force splitting into per-axis fields.
- Inner content preserved → the within-block local 4-tuple
  `(t%K, r%K, b%K, l%K)` passes through unchanged; only the block-grid
  position transforms.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    block_size: int
    block_d4: D4


CONSTS = Consts(block_size=2, block_d4=D4.FLIP_TB)


def solve(grid: Grid, c: Consts) -> Grid:
    k = c.block_size

    out: Grid = set()
    for ((t, b, l, r), col) in grid:
        # block_pos: a Position in the (H/k × W/k) block-grid.
        block_pos = (t // k, b // k, l // k, r // k)
        # Apply D4 in block-grid coords.
        (bt, bb, bl, br) = apply(c.block_d4, block_pos)
        # Recombine block-grid coords with per-block local.
        new_p = (bt * k + t % k, bb * k + b % k,
                 bl * k + l % k, br * k + r % k)
        out.add((new_p, col))
    return out
