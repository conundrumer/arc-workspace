# `frame_shift` — the displacements toward a direction that a frame admits

Every nonzero translation toward one direction that a frame's extent on that direction's axis allows, as a set of Offsets. A solver that moves content toward a direction and then tests each amount against what the grid holds reads its candidate amounts here, one Offset per amount, rather than as the cells a walk would pass over.

```
shift(Delta) :- in(P, _), move_dir(D), axis_of(D, A), sub_extent(P, A, K), jump_offset(D, K, Delta).
```

Not: `AxisFrame`, which yields the positions of an extent, not the shifts across it; `Slide`, which runs inside a node set the caller supplies and stops at that set's edge; `jump_offset` alone, which carries one amount that the caller already holds.

Match: a `sub_extent` whose amount reaches a `jump` or a `jump_offset` toward a Dir, directly or through one head column, where that Dir's axis is the `sub_extent`'s axis, tied by an `axis_of` atom or by a relation pairing an axis with a Dir on it, in the same rule or in a rule deriving one of the two; the amount reaches no `divide` atom. Grep `sub_extent`, then follow each amount's head column one hop; the parser matches both hops.

Survey: 2026-09-11 08:36 — the whole corpus.

Callers:
05f2a901 shift — the amounts the mover could slide toward the anchor, from the grid's extent on the move axis, filtered afterward by the case's contact test.
11dc524f shift — the amounts the shape could slide toward the mirror, from the grid's extent on the move axis, filtered afterward by the block's box.
84ba50d3 shift — the amounts a shape could fall toward `params.fall_dir`, filtered afterward by the cells that would leave the grid. The `axis_of` sits in the separate rule `fall_axis`, not in the shift rule.
981571dc cand — in Determine, the candidate offsets of the wallpaper's symmetry center from the grid center, on each axis; the rule leaves the Dir free under `axis_of`, so both directions of the axis land in one relation, and a second rule adds ORIGIN.
47996f11 cand — the same determination, for a pattern symmetric about an offset center.
af22c60d cand (one caller with its family sibling 3631a71a) — in Determine, the candidate mirror insets per axis, as a flush Dir and an amount k; the frame is `apos`, the set of axis-only positions, and `band_map` applies the amount with `jump`. A disjunct supplies k = 0.
337b420f slide — the amounts a piece could slide toward each Dir, from the per-choice frame `frame(Dc, P)`; `covered` applies the amount with `jump`, and a separate fact supplies k = 0.
18447a8d margin_cand — every margin a band frame admits along the axis of `params.piece_dir`; the frame is `box.inner`, and `landed` applies the amount with `jump` toward the opposite Dir.
136b0064 run_len — the step count of a cell a Slide run reached: the amounts toward D the canvas admits, applied to the start cell with `jump` to find the one that lands on that cell.
0dfd9992 axis_rep — inside the solver's `Wallpaper` proposal comp: the shifts toward each axis's canonical Dir that the keyed grid admits, filtered in the same rule to less than that axis's period. The axis-to-Dir tie is the comp's `canon` data relation, not `axis_of`, and a second rule supplies ORIGIN.

Near-misses:
045e512c toward, 0b17323b sep, 3979b1a8 cand — one class: a direction is bound and a displacement is formed, but the amount comes from either axis of the frame rather than from the direction's own axis. 045e512c enumerates over `dir8_elem` with step lengths from `span`; 0b17323b steps toward a `diag_dir_elem` with `jump`; 3979b1a8 jumps back toward the corner opposite its growth corner with `jump_delta`. For a cardinal Dir this admits amounts up to the perpendicular extent, and for a DiagDir there is no single axis to bound it; the operation's bound is the direction's own axis.
045e512c span, 25094a63 cand, 15113be4 cand, 83b6b474 cand_side, 8abad3cf cand_side, 50846271 arm, 456873bc side, 7b7f7511 tile_cell.item, 898e7135 scale_cand, 0934a4d8 cand_count, 1fad071e cand_dim, 2ccd9fef cand_tile, 6165ea8f cand_gap, 5833af48 pixel_cand, 5ad4f10b pixel_cand, 7b3084d4 square.extent, e9afcf9a tiled — one class: `sub_extent` under `axis_elem`, with no Dir. The amount is a candidate size, a tile count, or a period, and it feeds `divide`, `Frame2D`, or a comparison. No direction is bound and no displacement is formed, so these state no translation.
0934a4d8 ext_cand — binds a Dir with `axis_of` on the `sub_extent`'s axis, then forms an Inset with `edge_delta`: a margin from one edge, not a translation.
2c737e39 shift, 321b1fc6 shift, 34cfa167 shift, 4acc7107 move, 1caeab9d slide, 234bbc79 slide, 05a7bcf2 push_shift, 6ca952ad flush — one class: a single Shift read from a source and a target with `displacement`, or from a box margin with `jump_delta`. This is `jump_delta` alone, carrying an amount the caller already holds.
5ffb2104 room, 6ad5bdfd room — `dist(P, D, K), jump_delta(D, K, Delta)`: the shift that carries one cell to the frame edge, one amount per cell rather than the set the frame admits.
342dd610 move — reads K back off an existing Delta with `dist_pair`, the inverse direction of the operation.
05269061 period_jump, 29ec7d0e shift, ca8f78db period_delta, 484b58aa step, 0dfd9992 lat_ax, c1990cce march_jump, 5207a7b5 slant, 4364c1c4 moved — one class: the amount comes from a parameter, a tally, or a detected period, so no extent is enumerated.

Spec:
Sites beyond the surfacing solver carry changes to the interface, and answer questions about its range.

The output should carry the amount beside the Shift. Four caller families hold the amount in a head column: 337b420f `slide(dc, d, k)`, 18447a8d `margin_cand(k)`, af22c60d `cand(a, flush, k)` — where k is the parameter Determine reports — and 136b0064 `run_len(e, t, d, k, p)`. Six of the ten callers write the Shift as the entry's form gives it. A form yielding the direction, the amount, and the Shift together serves both groups; a Shift-only form leaves those four to re-derive k, or to use `jump` per cell and never form the Shift at all, which is what they do today.

The frame should be an input, and keyed. Only 05f2a901, 11dc524f, 84ba50d3, 47996f11 and 981571dc read the extent off `in` or `ex_out`. 18447a8d reads it off `box.inner`, af22c60d off `apos`, 136b0064 off a canvas cell, 0dfd9992 off its keyed `grid`, and 337b420f off `frame(Dc, P)`, which varies per decomposition choice and so needs the key. The entry's code form fixes the frame to `in`.

The direction should be a column of the output, not projected out. 981571dc and 47996f11 want every amount on both directions of an axis and key the result by Axis; 337b420f wants them keyed by Dir; 0dfd9992 takes one canonical Dir per axis and keys by Axis; the three move solvers bind one Dir from Params and project it out. A Dir-keyed output serves every one of those shapes.

The direction range stays cardinal, bounded by the direction's own axis. The three sites that form displacements toward a direction off the amount's own axis — 045e512c over `dir8_elem`, 0b17323b and 3979b1a8 over DiagDirs — each drop the axis bound to get there, so each takes either extent of the frame as a step length. That is a looser operation, and no caller asks for it.

The zero stays out. Five caller families state the no-move case themselves, each in one atom: 337b420f as a fact, af22c60d as a disjunct, 47996f11, 981571dc and 0dfd9992 as an ORIGIN rule. Under Zero is absence, that restatement is each caller's own claim that standing still is admitted, and folding it in would make the operation assert it for every caller.

The `Match:` line the survey ran did not meet its spec: it scoped the shape to one rule, and it missed the statements whose atoms sit in different rules. It matched only 05f2a901, 11dc524f, 136b0064, 47996f11 and 981571dc within a rule. 84ba50d3 puts the `axis_of` in `fall_axis`; 337b420f, af22c60d, 18447a8d and 045e512c export the amount through a head and consume it in a second rule; 0dfd9992 ties the axis to its Dir with a data relation, not `axis_of`. The `Match:` line above carries the signature that covers those forms.

Reimplementations: none. Across the corpus no site hand-writes an extent enumeration or a displacement that lib already holds: every candidate-amount site calls `sub_extent`, and every shift formation calls `jump_delta`, `jump`, `displacement` or `compose`. The search ran a parser matcher over every solver for the within-rule shape (31 rules in 30 solvers hold `sub_extent`; 5 matched), a second matcher for the one-hop shape (5 more), and a third for heads bound by `displacement` (109 sites, read down to the 8 named above), with greps over `jump_delta`, `axis_dim` and `axis_dims` to catch amounts formed without `sub_extent`.
