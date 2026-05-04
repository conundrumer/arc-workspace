"""Extract data cells from a 2D anchored stride layout.

Placeholders:
- position-destructure: arithmetic stride (`(H + s - 1) // s`, `dist // s`, `dist % s`) and hand-built Position via index-into-list-by-Dir.value. Conceptual primitive `repeat_anchored(cells, dir, span, margin) -> Cells[*Xs, local, tile]` would handle it. Second sample for the anchored-stride family (after ba26e723's 1D recolor; this is 2D and an extract).

Rule (Souffle form):
    in_h(H) :- in(P, _), H = dist(P, v_dir) + dist(P, v_opp) + 1.
    in_w(W) :- in(P, _), W = dist(P, h_dir) + dist(P, h_opp) + 1.
    out_h(O) :- in_h(H), O = ceil(H / c.stride).
    out_w(O) :- in_w(W), O = ceil(W / c.stride).
    out(make_pos(dist(P, v_dir) / c.stride,
                 dist(P, h_dir) / c.stride,
                 out_h, out_w), col)
        :- in(P, col),
           dist(P, v_dir) mod c.stride == 0,
           dist(P, h_dir) mod c.stride == 0.
    where (v_dir, h_dir) = c.anchor.value.

Tile every `stride` cells along each axis from the anchor; keep one cell
per tile (span = 1 implicit), discard margins. Output positions use the
tile index from the anchor side.

== Notes ==

- Consts: `anchor: DiagDir = TL` (family DOF — a TR/BR/BL-anchored
  sibling task reuses this body, swapping only the const) and
  `stride: int = 2` (= span 1 + margin 1; data on every other cell).

- Body uses `dist(p, dir)` for position access — Dir literals come from
  `c.anchor.value`, not inline. Position construction goes via
  index-into-list-by-Dir.value (same idiom as `corner_view`).

- bg color doesn't appear in the body — the rule is structural, not
  color-conditional. Margin cells are discarded by the stride filter
  regardless of their color. A variant where margins carry non-bg cells
  would still extract the data correctly.

- ceil(H/stride) computed as `(H + s - 1) // s`.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    anchor: DiagDir
    stride: int


CONSTS = Consts(anchor=DiagDir.TL, stride=2)


def solve(grid: Grid, c: Consts) -> Grid:
    s = c.stride
    v_dir, h_dir = c.anchor.value
    v_opp = opposite(v_dir)
    h_opp = opposite(h_dir)

    # Input dims along the anchor's axes.
    ((H, W),) = {
        (dist(p, v_dir) + dist(p, v_opp) + 1,
         dist(p, h_dir) + dist(p, h_opp) + 1)
        for (p, _) in grid
    }
    h_out = (H + s - 1) // s
    w_out = (W + s - 1) // s

    def make_pos(tv: int, th: int) -> Position:
        p = [0, 0, 0, 0]
        p[v_dir.value] = tv
        p[h_dir.value] = th
        p[v_opp.value] = h_out - 1 - tv
        p[h_opp.value] = w_out - 1 - th
        return (p[0], p[1], p[2], p[3])

    # out(make_pos(dist(P, v_dir) / s, dist(P, h_dir) / s), col)
    #   :- in(P, col), dist(P, v_dir) mod s == 0, dist(P, h_dir) mod s == 0.
    return {
        (make_pos(dist(p, v_dir) // s, dist(p, h_dir) // s), col)
        for (p, col) in grid
        if dist(p, v_dir) % s == 0 and dist(p, h_dir) % s == 0
    }
