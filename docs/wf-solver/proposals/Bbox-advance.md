# `Bbox.advance` — a set's own length as a displacement

A per-key readout on `Bbox`: the displacement toward `d` whose size is the set's own extent along `d`'s axis. Composed with any position, it steps that position one set-length on, so a solver that places content immediately beyond a set — the set itself moved off its own footprint, a copy stacked against it, a reflection seated past its far edge — states the placement in one atom. The known sites read the extent off the box, reselect the axis from the direction, and turn the number into a jump.

```
.decl advance(key: Key, d: Dir, delta: Shift)
advance(K, D, Delta) :- extent(K, A, N), axis_of(D, A), jump_delta(D, N, Delta).
```

Not: a jump of a stored or counted length (`jump`, `jump_delta`); a slide until contact (`Dock`); an extent used as a bound, a period, or a border width; `Bbox.margin` composed with another box's margin.

Match: a rule that binds `axis_of(D, A)` and a `Bbox` instance's `extent(_, A, N)` and feeds that `N` to `jump` or `jump_delta` toward the same `D`.

Survey: 2026-09-08 22:07

Callers:

- `5521c0d9` — `parse.moved`: each block cell carried the block's own extent, so the block sits directly beyond where it stood.
- `11dc524f` — `mirror`: the reflection's box sits one shape-length past the docked shape's box, so the two boxes meet at the mirror. The rule is the signature verbatim.
- `4acc7107` — `slot`: each next shape in a stack takes the corner one shape-depth past the shape before it, plus a gap. Direction and extent agree by construction — `stack_dir` comes from `diag_dirs` on the same axis — rather than through an `axis_of` atom.
- `22208ba4` — `moved_cell`: a corner block steps inward one block-length toward each edge of the opposite corner, as two `jump` atoms, one per axis.
- `22233c11` — `echo_cell`: a quadrant moves one quadrant-length outward along its own corner diagonal. One `jump_delta` stands for the two-axis advance only because a repeated variable states the quadrant is square.
- `447fd412` — `carry`: one step along the template corresponds to one block-side in the grid. A rewrite must keep the square guard as its own atom, since `advance` states no such thing.

Near-misses:

- Extent as a period — `53fb4810` `period`, `1ae2feb7` `claim`. The consumer takes a number, not a `Shift`. `53fb4810` is closest: its walk's first step is one band-length on.
- Extent as a margin or border width — `3a301edc` `thick.edge`, `2697da3f` `arm_depth.edge`. The result is an `Inset`.
- Extent as a bound — `3befdf3e` line 106.
- `4522001f` `sq_jump` — the operation, on a `MarginFrame` rather than a `Bbox`, with the extents from `axis_dims`. One site is not enough to move the operation off `Bbox`.
- Flush slides that jump by `Bbox.edge_min` — `05a7bcf2`, `320afe60`, `62b74c02`, `496994bd`, `20a9e565`.
- Counted lengths — `271d71e2` `advance` (an `Extremes` over a marker distance; a name collision at promotion), `8eb1be9a` `period.tally`, `12422b43` `pat_len`.

Spec question: widen `d` to `Dir8`, with the delta composed from the extent on each axis instead of one scalar. `22208ba4` and `22233c11` are corner moves that both diverge from the Dir-only form. Under it, `22208ba4` still spends three atoms for "one block-length toward the corner", and the entry's body cannot state the non-square diagonal case at all, since `jump_delta` carries one scalar to both axes. A per-axis definition gives the square case the same answer and the rectangular case the right one.

Survey: 2026-09-10 14:40 — the solvers since 2026-09-08 22:07, 045e512c, 0520fde7, 05f2a901, 08573cc6, 0c9aba6e, 0d87d2a6, 0dfd9992, 1190bc91, 11dc524f, 137f0df0, 13e47133, 142ca369, 1478ab18, 15113be4, 17829a00, 17cae0c1, 195ba7dc, 19bb5feb, 1a6449f1, 1acc24af, 1ae2feb7, 1b2d62fb, 1b60fb0c, 1c56ad9f, 1c786137, 1e32b0e9, 1f85a75f, 2037f2c7, 20818e16, 20981f0e, 212895b5, 22eb0ac0, 25c199f5, 264363fd, 291dc1e1, 29623171, 2bcee788, 2bee17df, 2c0b0aff, 2c181942, 3194b014, 31d5ba1a, 3428a4f5, 3490cc26, 34b99a2b, 36a08778, 36fdfd69, 3a25b0d8, 409aa875, 412b6263, 42a50994, 4364c1c4, 446ef5d2, 44f52bb0, 465b7d93, 4938f0c2, 4aab4007, 4c3d4a41, 4c416de3, 4c5c2cf0, 4e34c42c, 4e45f183, 4e7e0eb9, 4ff4c9da, 506d28a5, 50846271, 516b51b7, 54db823b, 54dc2872, 5521c0d9, 5545f144, 5587a8d0, 5614dbcf, 5623160b, 56dc2b01, 56ff96f3, 5751f35e, 5792cb4d, 57aa92db, 57edb29d, 581f7754, 5833af48, 58490d8a, 58743b76, 58c02a16, 58e15b12, 58f5dbd5, 5961cc34, 5a5a2103, 5a719d11, 5ad4f10b, 5ad8a7c0, 5adee1b2, 5af49b42, 5b37cb25, 5b526a93, 5b692c0f, 5c0a986e, 5c2c9af4, 5d2a5c43, 5d588b4d, 5daaa586, 5dbc8537, 5e6bbc0b, 5ecac7f7, 5ffb2104, 604001fa, 60a26a3e, 60b61512, 60d73be6, 6165ea8f, 623ea044, 62593bfd, 626c0bcc, 62ab2642, 6350f1f4, 63613498, 639f5a19, 642248e4, 6455b5f5, 64a7c07e, 64efde09, 652646ff, 65b59efc, 668eec9a, 66ac4c3b, 673ef223, 67636eac, 67a423a3, 67c52801, 67e490f4, 6855a6e4, 689c358e, 68bc2e87, 692cd3b6, 694f12f3, 696d4842, 69889d6e, 6a1e5592, 6a980be1, 6aa20dc0, 6ad5bdfd, 6b9890af, 6bcdb01e, 6c434453, 6ca952ad, 6cbe9eb8, 6cdd2623, 6d0160f0, 6d58a25d, 6df30ad6, 6e19193c, 6e453dd6, 6e4f6532, 6e82a1ae, 6ecd11f4, 6f473927, 6ffbe589, 6ffe8f07, 7039b2d7, 71e489b6, 72322fa7, 72a961c9, 72ca375d, 73c3b0d8, 73ccf9c2, 7447852a, 7491f3cf, 753ea09b, 758abdf0, 759f3fd3, 75b8110e, 760b3cac, 762cd429, 7666fa5d, 770cc55f, 776ffc46, 780d0b14, 782b5218, 78332cb0, 7837ac64, 78e78cff, 79369cc6, 794b24be, 79fb03f4, 7acdf6d3, 7b0280bc, 7b3084d4, 7b5033c1, 7b6016b9, 7b80bb43, 7bb29440, 7c008303, 7c66cb00, 7c8af763, 7c9b52a0, 7d18a6fb, 7d1f7ee8, 7d419a02, 7d7772cc, 7ddcd7ec, 7df24a62, 7e0986d6, 7e2bad24, 7e576d6e, 7ec998c9, 7ed72f31, 7ee1c6ea, 7f4411dc, 800d221b, 80214e03, 80a900e0, 80af3007, 810b9b61, 817e6c09, 81c0276b, 825aa9e9, 82819916, 83302e8f, 83b6b474, 83eb0a57, 8403a5d5, 84551f4c, 845d6e51, 846bdb03, 85c4e7cd, 89565ca0, 9565186b, 97999447, 99b1bc43, b1fc8b8e, b7cb93ac, bbc9ae5d, bdad9b1f, ce4f8723, cf98881b, d19f7514, d9fac9be, dae9d2b5, e133d23d, e345f17b, e9afcf9a, f2829549, fafffa47.

## 1. Callers

Signature matched over all 244 solvers in scope: every `jump`/`jump_delta`/`edge_delta`/`axis_delta`/`displacement` atom, and every `Bbox` `extent`/`extents` and `axis_dim(s)` readout, checked for variable flow within a rule and one hop across rules. Five sites state the operation.

1. `5521c0d9` — `parse.moved` (`/Users/davidlu/code/arc-workspace/programs/solvers/5521c0d9.dl` lines 32–36): each block cell is carried its block's own extent along the move direction, so the block sits directly beyond where it stood. The rule is the signature verbatim (`axis_of`, `box.extent`, `jump`).
2. `11dc524f` — `mirror` (`/Users/davidlu/code/arc-workspace/programs/solvers/11dc524f.dl` lines 62–65): the reflection's box is the docked shape's home box moved one shape-length along the slide, so the two boxes meet at the mirror. Signature verbatim.
3. `64a7c07e` — `landed` (`/Users/davidlu/code/arc-workspace/programs/solvers/64a7c07e.dl` lines 28–31): each blob cell moves one blob-length along `params.move_dir`. Signature verbatim.
4. `58e15b12` — `trace` (`/Users/davidlu/code/arc-workspace/programs/solvers/58e15b12.dl` lines 31–36): each repeat of a bar sits one bar-length on along the bar axis (and one cell wider across it), recursively until the frame ends. The axis comes from `params.bar_axis` and `D_step` is tied to it in the base rule via `axis_of`; the recursive rule reads `box.extent(Col, A, N), jump(P, D_step, N, P_on)`. A copy stacked against the set, per the entry's body.
5. `045e512c` — `step` under `$Abut` (`/Users/davidlu/code/arc-workspace/programs/solvers/045e512c.dl` lines 82–86): the march step is the template's extent toward `D` plus a stored gap, `sbox.extents($U(), _, N, N), toward(D, N, S1), params.gap(G), toward(D, G, S2), compose(S1, S2, Delta)`. `toward` is `jump_delta` over `dir8_elem`, so `D` is a `Dir8`, and the repeated `N, N` states the template is square, the same shape as the entry's `22233c11` site, with the gap composed as at `4acc7107`.

Of the entry's recorded callers, `4acc7107`, `22208ba4`, `22233c11`, and `447fd412` are outside this scope and were not rechecked.

## 2. Near-misses

1. `7447852a` — `params.period` and `mark_cell` (`/Users/davidlu/code/arc-workspace/programs/solvers/7447852a.dl` lines 38–39, 76–79): the stamp's extent along the anchor axis, read with `axis_dim` off a stored stamp, jumped both ways along the strip. Excluded as an extent used as a period, and the extent is read off a stored grid, not a `Bbox`.
2. `1ae2feb7` — `claim` (line 84): `run_box.extent` fed to `stride`. Extent as a period; the consumer takes a number.
3. `58c02a16` — `phase` (line 50): `block.extents` fed to `stride` as the fine period. Extent as a period.
4. `6a980be1` — `strip_out` (lines 55–57): `axis_of(D, A), jump(P, D, K, P2)` where `K` is `ShiftInvariance.min_period`. A counted length, not an extent.
5. `7d419a02` — `step` and `shade` (lines 108–109, 127): `unit.extent` compared with a ray distance, `K <= W`. Extent as a bound.
6. `5623160b` `ink` (line 78), `62593bfd` `paint` (line 86), `6ca952ad` `flush` (line 37): `Bbox.edge_min` jumped toward `d`. Flush slides, the `Bbox.flush` entry, not an extent.
7. `05f2a901` `shift` (line 86), `11dc524f` `shift` (line 36), `0dfd9992` `axis_rep` (lines 50–53): `sub_extent` of the frame fed to `jump_delta`. Enumerates every displacement the frame admits, not one set-length.
8. `08573cc6` `arm` (line 57), `4364c1c4` `moved`/`slide_map` (lines 80, 108), `825aa9e9` (line 75), `409aa875` (lines 112, 148): jumps of a stored length (`len0`, `shift`, `gap`, `reach`).
9. `5c2c9af4` — `spread` (line 37): `displacement` from the center to `box.margin`, an `Inset` that grows outlines. A margin composition, not an extent.
10. `64efde09` `lane_color` (line 90), `689c358e` `points` (line 46): `extents` compared to pick the long or short axis, then `axis_of`; no displacement follows.

## 3. Spec

The entry's open question is whether to widen `d` to `Dir8` with a per-axis delta. This scope adds one site on the widening side, `045e512c`, which is not the surfacing solver: its `toward` ranges over `dir8_elem`, so the Dir-only definition cannot state its diagonal steps, and it states the square case by a repeated variable exactly as `22233c11` does. Under a per-axis definition, `045e512c` would read `sbox.advance($U(), D, S1)` and drop the `extents` readout, while keeping the gap `compose` as its own atom. The four other callers in scope are all cardinal and fit either definition. The gap in `045e512c` and the perpendicular `neighbor` in `58e15b12` compose after the advance and need no interface change.

`7447852a` is a second site, after the entry's `4522001f`, that reads the extent off something other than a `Bbox`; both are excluded (period; MarginFrame), so they do not move the operation off `Bbox`.

## 4. Reimplementations

Reimplementations: none.
