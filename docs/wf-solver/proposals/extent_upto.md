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

Survey: 2026-09-10 09:09
