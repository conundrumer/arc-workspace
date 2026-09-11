# `extent_upto` — every extent up to the frame's own

Every extent along an axis that a frame admits, its own extent included: each k with 1 <= k <= the frame's extent along that axis. `sub_extent` states the strict peer, which stops one short, so a solver that sweeps candidate sizes and must keep the whole frame as one of them writes the two together. The known sites write the disjunction.

```
( sub_extent(P, A, K) ; axis_dim(P, A, K) )
```

Not: `sub_extent` alone (the proper sub-extents); `axis_dim` alone (the frame's own extent); `PixelScale.md`, which records this disjunction inside a larger operation — the sweep of block sizes with a uniformity test and a pick.

Match: a rule that derives an extent for one position and axis from both a `sub_extent` atom and an `axis_dim` atom, whether the two sit in the branches of one disjunction, in separate lines of one rule, or in separate rules under one head. Loose tier: any relation with a number column fed by `sub_extent` in one rule and by `axis_dim` in another, over the same position and axis.

Sites:

- 83b6b474.dl:30-34 — `cand_side`: the input's extents and every shorter one, as candidate square sides.
- 5833af48.dl:117-118 — `pixel_cand`: a pixel size the plan's extent admits, the whole plan being one pixel across.
- 5ad4f10b.dl:89-90 — `pixel_cand`: the same sweep over the drawing's extent.

Survey: 2026-09-10 21:30 — the whole corpus.

Callers:
83b6b474 cand_side — every extent of the input frame and every shorter one, as candidate square sides, written as the disjunction `( axis_dim(P, A, K) ; sub_extent(P, A, K) )` over `in` cells and `axis_elem`.
8abad3cf cand_side — every extent of the input frame and every shorter one, as candidate square sides, the disjunction over `in` cells and `axis_elem`, feeding a `Frame2D<number>` of squares.
898e7135 scale_cand — the scale factors a piece admits: an extent of its `BoxFrame` box or less, the disjunction over `piece_box.inner` cells and `axis_elem`, feeding a `Frame2D<number>` of blocks.
5833af48 pixel_cand — a pixel size the plan's extent admits per axis, the disjunction over `plan_cell` narrowed by `divide_by_size`; `PixelScale.md` lists this site inside its larger operation.
5ad4f10b pixel_cand — the same per-axis pixel sweep over `drawing` cells, narrowed by `divide_by_size`; also a `PixelScale.md` site.

None of the five carries a `// family:` line, so each counts as one caller. Three sites (83b6b474, 8abad3cf, 898e7135) collapse the axis existentially into one scalar candidate set; two (5833af48, 5ad4f10b) keep the axis in the head.

Near-misses:
The zero-anchored dual, every offset from 0 up to but excluding the frame's extent, is the disjunction's mirror at the other end and is ruled out by the operation's definition (1 <= k <= extent): 3631a71a cand and af22c60d cand write `( K = 0 ; sub_extent(Along, A, K) )`; 47996f11 cand and 981571dc cand write `sub_extent` in one rule and `cand(A, ORIGIN)` in a second rule under the same head; 0dfd9992 axis_rep writes `axis_rep(Key, A, ORIGIN)` as a fact-shaped rule beside a `sub_extent` rule bounded by a period.
456873bc side — `sub_extent` alone produces the candidate; the `axis_dims` atom in the rule reads the tile arrangement's frame, a different position, not the swept frame, so the whole input extent is never a candidate. Ruled out by `sub_extent` alone.
1fad071e cand_dim — commented as "every size an input frame admits" but written with `sub_extent` alone, so the whole frame is excluded. Ruled out by `sub_extent` alone.
The other candidate sweeps on `sub_extent` alone, where excluding the frame's own extent is the intended strict sweep: 0934a4d8 ext_cand and cand_count, 15113be4 cand, 18447a8d margin_cand, 25094a63 cand, 2ccd9fef cand_tile, 3979b1a8 cand, 6165ea8f cand_gap, 7b3084d4 square.extent. Each ruled out by `sub_extent` alone.

Spec:
The interface holds as an inline peer of `sub_extent`, `extent_upto(p, a, k)`, with the frame read off any of its positions: all five callers ground the position from a cell of the swept frame and bind the axis from `axis_elem`, exactly as they feed `sub_extent`. The callers split on whether the axis survives into the head (per-axis pixel sizes at 5833af48 and 5ad4f10b; a scalar side collapsed over both axes at 83b6b474, 8abad3cf, 898e7135), and the per-cell inline form serves both without change, so no keyed comp form is warranted. The two `PixelScale.md` callers would stop writing the disjunction if that comp were promoted with `cand` holding the whole extent, as its spec question records; the three square-side callers have no such larger operation and are the evidence that the operation stands on its own. The near-miss class at 3631a71a, af22c60d, 47996f11, 981571dc, and 0dfd9992 shows a second two-ended sweep, offsets `0 <= k < extent`, that the `Not:` line does not yet name; naming it there would keep the next survey from reading those five sites as hits.

Reimplementations: none.
Matcher: a parser scan under the scratch path over all 733 solvers. Strict tier (one rule holding a bare `sub_extent` atom and a bare `axis_dim` or `axis_dims` atom on the same position and axis variables): 5 hits, the five callers. Loose tier (one head fed by `sub_extent` in one rule and `axis_dim` in another, on the same position and axis): 0 hits. Comparison-bounded sweep (`axis_dim` extent bounding another number by `<=`, `<`, `>=`, `>` in one rule): 0 hits. Rules with `sub_extent` and no extent readout: 25 rules across 24 solvers, each read in its rule; the near-misses above are the ones that sweep candidates.
