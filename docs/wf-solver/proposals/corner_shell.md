# `corner_shell` — the Chebyshev distance to a corner

The greater of a position's two distances to a corner's edges: the index of the nested L-shell the position sits on, counting out from the corner cell at 0. It is the L∞ peer of `corner_dist`, whose level sets are the anti-diagonal lines; the level sets here are the L-shells, so equality names a shell and comparison names which side of a shell a cell falls on.

```
.decl corner_shell(p: Position, diag: DiagDir, k: number) inline
corner_shell(P, Diag, K) :- diag_dist(P, Diag, _, K, K2), K2 <= K.
```

Not: `corner_dist` (taxicab distance to a corner); `edge_depth` (the least over all four edges); `Diagonal.diagonal` and `DiagPlacement.diag_cell` (the ring where the two distances are equal — the corner diagonal alone); `diag_dist` (both distances, in both orders, with no pick); `axis_near` and `axis_far` (the two edges of one axis); a corner's two distances bounded per axis, which states a rectangle rather than a shell.

Match: a rule holding `diag_dist`, or two `dist` atoms at the two dirs of one corner, whose two distance variables either feed one `<=` or `>=` against each other with the kept variable read as a value, or feed one shared scalar bound. Grep `diag_dist` and confirm the comparison and the read.

Survey: 2026-09-08 20:52

Result: over the corpus, `diag_dist` appears at 13 sites in 10 files. Five sites in four files order one position's two corner-edge distances against each other, directly or through a helper relation; one further site bounds both by one shared scalar. Of those, two read the greater and are the operation, two read the lesser, and two keep both. The 19 sites that order a `dist_pair` are all the two edges of one axis, which the `Not:` line excludes.

Near-misses:

- `4aab4007` `Determine.steady.item` and `legend_cell` keep both distances — `Determine.steady.item` orders them into a canonical key, and `legend_cell` matches a stored pair in both orders — so a single-value readout does not serve them.
- `79cce52d` `kept` states that the lesser distance is nonzero, which the greater alone does not state.
- `0becf7df` `key_cell` and `332efdb3` `window` bound the two distances by per-axis extents. The block is rectangular and the axis tag is load-bearing, so the greater does not decide membership.
- `1478ab18` `right_angle` orders one corner's two `diag_dist` distances and reads neither as a value: a sidedness test against that corner's diagonal, not a shell index.
- `212895b5` `place` carries both distances into head columns and bounds a wedge with the comparison.
- `52df9849` orders `corner_dist` across two positions — taxicab, and between cells rather than within one.
- `6e02f1e3`, `3979b1a8`, `3bd67248`, and `8618d23e` write `diag_dist` with a repeated distance variable, which is the corner diagonal.
- `85c4e7cd`, `3ee1011a`, and `4290ef0e` read concentric rings through `Rim.depth`, the least over all four edges.

Spec question: whether the operation is the greater distance alone, or an ordered `(near, far)` readout — the corner peer of the `axis_near`/`axis_far` pair.

```
.decl corner_near_far(p: Position, diag: DiagDir, near: number, far: number) inline
corner_near_far(P, Diag, K1, K2) :- diag_dist(P, Diag, _, K1, K2), K1 <= K2.
```

The survey argues for the pair, on four grounds. Four sites in three solvers want the lesser or both, against two that want the greater. A wildcard on the unwanted column serves every one of those sites, so the pair loses nothing the greater-only form has, while the greater-only form serves neither `4aab4007` nor `79cce52d`. The pair also removes a stated workaround: `4aab4007`'s `params.legend` reads a stored pair in both orders so that a row covers its reflection, and a canonical key retires that. And lib already treats one axis this way — `dist_pair` yields both distances and `axis_near`/`axis_far` are its sorted readout, so the corner peer of `diag_dist` is the missing unit.

Callers:

- 539a4f51 — `shell`, the L-shell index of a cell, read off the input to find each shell's color and off the output frame to place it. The one site that wants the greater alone.
- 87ab05b8 — `region` under `$Corner()`, the square block of side `params.block_dim` at a marker's nearest corner, written as both distances under one scalar bound. Served as `corner_shell(P, Diag, K), K < N`.
