"""Top H-1 input rows kept; last row derived.

Placeholders:
- position-destructure: TOP-anchored row carry into a fixed-height output, row-recolor against bg color, inline (1,1) bg-anchor read. No anchored-carry / row-recolor primitives. Layout-family cluster (header/body section split, à la `bd4472b8`'s body_start).

Rule (Souffle form):
    in_w(W) :- in((_, R, _, L), _), W = R + L + 1.
    bg(C)   :- in((1, _, _, 1), C).
    out((T, W-1-L, H-1-T, L), C) :- in((T, _, _, L), C), T < H-1, in_w(W), out_h(H).
    out((H-1, W-1-L, 0, L), C)   :- in((0, _, _, L), C),  bg(C), in_w(W), out_h(H).
    out((H-1, W-1-L, 0, L), M)   :- in((0, _, _, L), C), !bg(C), marker(M), in_w(W), out_h(H).

Datalog-lite (Python) form, with the projection forced by the host:
    bg_proj(C) :- bg(C).
    out((H-1, W-1-L, 0, L), M) :- in((0, _, _, L), C), !bg_proj(C), marker(M).

Output dims: (out_h, in_w). Height is a per-task constant; width matches input.

== Notes ==

- TOP bias is rule-level: input rows 0..H-2 carry to output rows 0..H-2,
  and the last row is derived from input row 0. The position remap
  (T, _, _, L) → (T, W-1-L, H-1-T, L) translates between coordinate
  systems with different heights. Edge dir (TOP) would belong in Consts
  under a `carry_anchored(cells, dir, n, out_h)`-shaped primitive.

- bg is read from cell (top=1, left=1) — the TL of the bulk region (rows
  body_start.., cols 1..). Equivalent framing: "the most-frequent color in
  input." Deferred which generalizes.

- Row-recolor mirrors b1948b0a's mapping shape, but the !mapping branch
  produces a constant marker color rather than identity. A two-row mapping
  `{(bg, bg), (*, marker)}` doesn't fit because mapping keys must be
  enumerable Colors, not "anything else". Currently inlined.

- Consts: `out_h: int = 3` (the per-task output height; lifted from the
  body so the rule isn't baked into magic numbers), and `marker: Color = C6`.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    out_h: int
    marker: Color


CONSTS = Consts(out_h=3, marker=C6)


def solve(grid: Grid, c: Consts) -> Grid:
    H = c.out_h

    # in_w(W) :- in((_, R, _, L), _), W = R + L + 1.
    (W,) = {l + r + 1 for ((_, r, _, l), _) in grid}

    # bg(C) :- in((1, _, _, 1), C).
    (bg,) = {col for ((t, _, _, l), col) in grid if t == 1 and l == 1}

    # out((T, W-1-L, H-1-T, L), C) :- in((T, _, _, L), C), T < H-1.
    keep = {((t, W - 1 - l, H - 1 - t, l), col) for ((t, _, _, l), col) in grid if t < H - 1}

    # bg_proj(C) :- bg(C).
    # out((H-1, W-1-L, 0, L), C) :- in((0, _, _, L), C),  bg(C).
    # out((H-1, W-1-L, 0, L), M) :- in((0, _, _, L), C), !bg_proj(C), marker(M).
    derived = {
        ((H - 1, W - 1 - l, 0, l), col if col == bg else c.marker)
        for ((t, _, _, l), col) in grid
        if t == 0
    }

    return keep | derived
