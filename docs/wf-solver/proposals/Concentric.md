# `Concentric<Key>` — the boxes one repeated inset generates

The family of boxes a seed box generates under one repeated inset, per key: each box is the one before it let out by that inset, and the run ends where a box covers no cell of the domain. A solver that draws rings at a fixed spacing, or that reads which ring a cell sits on under such a family, names the family in one instance instead of closing the inset in a rule of its own.

Solver-local form (5c2c9af4), where the seed is the center cell as a degenerate box, the inset carries the center out to the innermost ring, and the clip is mutual recursion with `BoxCells` — the run continues from a box that still draws a cell:

```
.decl outline(b: Position)
outline(B) :- center(B).
outline(B2) :- bcells.on_edge(B, _, _), spread(V), compose(B, V, B2).

.init bcells = BoxCells<Position>
bcells.box(B, B) :- outline(B).
bcells.cell(B, P) :- outline(B), in(P, _).
```

Comp form:

```
.comp Concentric<Key> {
    // The box the family runs from, per key.
    .decl seed(key: Key, b: Position)  // input

    // The inset from each box to the next, per key.
    .decl step(key: Key, v: Inset)     // input

    // The cells the family is read over, per key.
    .decl cell(key: Key, p: Position)  // input

    // The seed, and every box the step reaches from it. A box covering no
    // cell ends the run, and so does every box beyond it.
    .decl box(key: Key, b: Position)
}
```

Not: `Outset` (one box let out, with the band between the two read off it); `LatticeOrbit` (a translation lattice over frame cells, whose `(axis, period)` generator states a shift and cannot state an inset); `BoxCells` (the cells of one box); `edge_depth` and `corner_shell` (a cell's ring index under a family anchored on the frame or on a corner, with no seed and no spacing); `Rim.depth` (rings that follow a set's own shape); one inset with no closure over it.

Match: a head-recursive rule over a Position read as margins whose step composes a fixed `Inset`. Grep: `uniform_delta`, `compose(` and `displacement(` sites whose box argument comes from `Bbox.margin` or from a relation the same rule heads. Shape: a rule whose head relation occurs in its body, where the recursive Position column also feeds `BoxCells.box`, `Bbox.margin`, `BoxCells.hole`, or `geq` as margins.

Spec questions:

- Whether `box` carries a ring index beside the box, for a caller that colors or selects per ring.
- Whether the run goes both ways from the seed, or one way along the inset as written.
- Whether the clip is "the box covers a domain cell" or a margin test against the frame.

Survey: 2026-09-09 02:56

The survey read the whole corpus, 584 solvers. A head-recursion test alone misses 5c2c9af4, whose recursion passes through its `BoxCells` instance, so the shape matcher collapsed each comp instance to one node, took the recursive cycles over that graph, and kept the cycles holding a step atom together with a box-as-margins consumer. That signature matched 12 files. Besides 5c2c9af4, three of them close a step over a box or over a box's placement — 4522001f `fit_box`, 28e73c20 `walk`, and 16b78196 `seat_step` — and each is a near-miss below. The remaining eight close over cells. Of the 10 `uniform_delta` lines in the corpus, every one but 28e73c20's is a single placement or a depth-to-box conversion with no closure. Of the 27 rules holding a box margin together with `compose` or `displacement`, every one but 5c2c9af4's two translates a box by a Shift, seats content in a box frame, or reads the offset between two boxes.

Near:

- 28e73c20 `walk` closes `params.inset` over the spiral's turn box, one inset per cycle. The box family is the walk's own state, and the consumer needs each box paired with the walk step standing on it, which a `box` set with neither index nor successor cannot give.
- 4522001f `fit_box` writes the spec's rule shape exactly — a seed from `sq.margin`, a recursive `compose` of one fixed delta, and a clip — but the delta is a Shift built from two `jump_delta`s, so the family marches along the diagonal at constant size instead of nesting. Its `grow_box` is the same rule with the recursion dropped.
- 5587a8d0 `covers` grows a nested-ring family from a degenerate seed at ORIGIN, by a `dir8_elem` dilation over a set of Shifts rather than an inset onto a box, and its run length is the patch count along `nest.next` rather than a clip.
- 16b78196 `seat_step` composes `box.margin` with a placement delta and clips by `geq(M2, ORIGIN)`, but its recursion carries that delta rather than the box, and the step varies per host-and-piece contact, so no single delta generates the run.
- 5751f35e `layer` converts a `Rim` depth into a box with `uniform_delta` and reads cells off it with `geq` — the closest the corpus comes to `box` as a readout — with no seed, no spacing, and no closure.
- The classes the `Not:` line already names: one box let out with no closure (3a301edc, 52fd389e, 543a7ed5, 58f5dbd5, 49d1d64f, 412b6263, ed74f2f2); rings at spacing 1 off the frame or a set's own shape (85c4e7cd, 45a5af55, 3ee1011a, 4290ef0e, 5751f35e `peel`, 516b51b7, 13e47133, 52364a65, 522fdd07); nested L-shells at a corner (539a4f51) and rings about a corner (ca8de6ea); `BoxCells` over one box per key (1a6449f1, 1c786137, 4c7dc4dd, 5b526a93); a box-shaped cell set translated once (2b9ef948); and a nest that arrives as data (40f6cd08, 3befdf3e).

Spec: every signal the three questions could take rests on the one caller. On a ring index, the two sites that would need the family ordered are 28e73c20 and 5587a8d0, and each is a near-miss on an independent ground, so neither becomes a caller if the index is added. No site in the corpus runs a box family both ways. On the clip, 4522001f is the one other clipped box run and it writes the margin test, but its Shift step rules it out; 5c2c9af4's own outlines continue past the grid edge and draw partial rings, which `geq(B, ORIGIN)` would cut short.

Survey: 2026-09-09 03:12

A delta over the eight solvers written or edited after the first survey's time — 5daaa586, 5d588b4d, 4ff4c9da, 5dbc8537, bdad9b1f, 22eb0ac0, 137f0df0, 5e6bbc0b. No caller, no reimplementation, and no signal on the three questions: no site in that scope runs a box family, and no recursion cycle in it carries a Position. Its nearest site is 5daaa586's `box`, a `BoxCells<Unit>` fed from `crop.margin` — the caller's own wiring, over a single box with no step to repeat, so it joins the `BoxCells` class the `Not:` line names.

Callers:

- `programs/solvers/5c2c9af4.dl` — `outline` with its `BoxCells<Position>` instance. The seed is the center cell as a degenerate box, the inset carries the center out to the innermost ring, and the run ends where an outline draws no grid cell.

Survey: 2026-09-10 15:18 — the solvers since 2026-09-09 03:12, 009d5c81, 00dbd492, 045e512c, 0520fde7, 05f2a901, 08573cc6, 0934a4d8, 0962bcdd, 0c9aba6e, 0ca9ddb6, 0d87d2a6, 0dfd9992, 10fcaaa3, 1190bc91, 11dc524f, 136b0064, 137f0df0, 13e47133, 142ca369, 14754a24, 1478ab18, 15113be4, 15663ba9, 16de56c4, 17829a00, 178fcbfb, 17b866bd, 17cae0c1, 1818057f, 18286ef8, 182e5d0f, 18419cfa, 18447a8d, 195ba7dc, 195c6913, 1990f7a8, 19bb5feb, 1a07d186, 1a6449f1, 1acc24af, 1ae2feb7, 1b2d62fb, 1b59e163, 1b60fb0c, 1bfc4729, 1c02dbbe, 1c56ad9f, 1c786137, 1caeab9d, 1d0a4b61, 1d398264, 1d61978c, 1e32b0e9, 1e5d6875, 1e97544e, 1efba499, 1f0c79e5, 1f642eb9, 1f85a75f, 1f876c06, 2037f2c7, 20818e16, 20981f0e, 20fb2937, 212895b5, 21897d95, 21f83797, 2204b7a8, 221dfab4, 22208ba4, 22233c11, 22425bda, 22806e14, 22eb0ac0, 234bbc79, 239be575, 23b5c85d, 247ef758, 25094a63, 252143c9, 253bf280, 2546ccf6, 256b0a75, 25c199f5, 25d487eb, 25e02866, 2601afb7, 264363fd, 2685904e, 2697da3f, 269e22fb, 272f95fa, 2753e76c, 278e5215, 27a28665, 27a77e38, 27f8ce4f, 281123b4, 28e73c20, 291dc1e1, 292dd178, 29623171, 29700607, 2a5f8217, 2b01abd0, 2b83f449, 2ba387bc, 2bcee788, 2bee17df, 2c0b0aff, 2c181942, 2c608aff, 2c737e39, 2dc579da, 2e65ae53, 2f0c5170, 2f767503, 2faf500b, 305b1341, 3194b014, 31aa019c, 31d5ba1a, 320afe60, 321b1fc6, 332202d5, 3345333e, 337b420f, 3391f8c0, 33b52de3, 3428a4f5, 342ae2ed, 3490cc26, 34b99a2b, 34cfa167, 351d6448, 358ba94e, 3631a71a, 363442ee, 36a08778, 36d67576, 36fdfd69, 37d3e8b2, 38007db0, 396d80d7, 39a8645d, 39e1d7f9, 3a25b0d8, 3a301edc, 3aa6fb7a, 3ac3eb23, 3ad05f52, 3bd292e8, 3bdb4ada, 3befdf3e, 3d31c5b3, 3d588dc9, 3d6c6e23, 3dc255db, 3e6067c3, 3e980e27, 3ed85e70, 3eda0437, 3ee1011a, 3f23242b, 40853293, 4093f84a, 409aa875, 40f6cd08, 412b6263, 414297c0, 41ace6b5, 4258a5f9, 4290ef0e, 42918530, 42a15761, 42a50994, 42f14c03, 42f83767, 4364c1c4, 444801d8, 445eab21, 446ef5d2, 447fd412, 44d8ac46, 44f52bb0, 4522001f, 456873bc, 45737921, 458e3a53, 45a5af55, 45bbe264, 4612dd53, 465b7d93, 469497ad, 46c35fc7, 46f33fce, 477d2879, 47996f11, 47c1f68c, 4852f2fa, 48634b99, 48d8fb45, 48f8583b, 4938f0c2, 494ef9d7, 4a1cacc2, 4a21e3da, 4aab4007, 4acc7107, 4b6b68e5, 4be741c5, 4c177718, 4c3d4a41, 4c416de3, 4c5c2cf0, 4c7dc4dd, 4df5b0ae, 4e34c42c, 4e45f183, 4e469f39, 4e7e0eb9, 4f537728, 4ff4c9da, 5034a0b5, 506d28a5, 50846271, 508bd3b6, 50a16a69, 50aad11f, 50c07299, 50f325b5, 5117e062, 5168d44c, 516b51b7, 5207a7b5, 522fdd07, 52364a65, 5289ad53, 52df9849, 52fd389e, 538b439f, 539a4f51, 53fb4810, 543a7ed5, 54d82841, 54d9e175, 54db823b, 54dc2872, 55059096, 551d5bf1, 5521c0d9, 5545f144, 55783887, 5587a8d0, 5614dbcf, 5623160b, 56dc2b01, 56ff96f3, 5751f35e, 5792cb4d, 57aa92db, 57edb29d, 581f7754, 5833af48, 58490d8a, 58743b76, 58c02a16, 58e15b12, 58f5dbd5, 5961cc34, 5a5a2103, 5a719d11, 5ad4f10b, 5ad8a7c0, 5adee1b2, 5af49b42, 5b37cb25, 5b526a93, 5b692c0f, 5c0a986e, 5c2c9af4, 5d2a5c43, 5d588b4d, 5daaa586, 5dbc8537, 5e6bbc0b, 5ecac7f7, 5ffb2104, 604001fa, 60a26a3e, 60b61512, 60d73be6, 6165ea8f, 623ea044, 62593bfd, 626c0bcc, 62ab2642, 6350f1f4, 63613498, 639f5a19, 642248e4, 642d658d, 6430c8c4, 6455b5f5, 64a7c07e, 64efde09, 652646ff, 65b59efc, 662c240a, 668eec9a, 66ac4c3b, 66e6c45b, 66f2d22f, 673ef223, 67636eac, 6773b310, 67a423a3, 67c52801, 67e490f4, 6855a6e4, 689c358e, 68b67ca3, 68bc2e87, 692cd3b6, 694f12f3, 696d4842, 69889d6e, 6a11f6da, 6a1e5592, 6a980be1, 6aa20dc0, 6ad5bdfd, 6b9890af, 6bcdb01e, 6c434453, 6ca952ad, 6cbe9eb8, 6cdd2623, 6d0160f0, 6d58a25d, 6df30ad6, 6e19193c, 6e453dd6, 6e4f6532, 6e82a1ae, 6ecd11f4, 6f473927, 6ffbe589, 6ffe8f07, 7039b2d7, 71e489b6, 72322fa7, 72a961c9, 72ca375d, 73c3b0d8, 73ccf9c2, 7447852a, 7491f3cf, 74dd1130, 753ea09b, 758abdf0, 759f3fd3, 75b8110e, 760b3cac, 762cd429, 7666fa5d, 770cc55f, 776ffc46, 780d0b14, 782b5218, 78332cb0, 7837ac64, 78e78cff, 79369cc6, 794b24be, 79fb03f4, 7acdf6d3, 7b0280bc, 7b3084d4, 7b5033c1, 7b6016b9, 7b80bb43, 7bb29440, 7c008303, 7c66cb00, 7c8af763, 7c9b52a0, 7d18a6fb, 7d1f7ee8, 7d419a02, 7d7772cc, 7ddcd7ec, 7df24a62, 7e02026e, 7e0986d6, 7e2bad24, 7e576d6e, 7ec998c9, 7ed72f31, 7ee1c6ea, 7f4411dc, 800d221b, 80214e03, 80a900e0, 80af3007, 810b9b61, 817e6c09, 81c0276b, 825aa9e9, 82819916, 83302e8f, 833966f4, 83b6b474, 83eb0a57, 8403a5d5, 84551f4c, 845d6e51, 846bdb03, 85c4e7cd, 89565ca0, 8e5a5113, 94f9d214, 9565186b, 97999447, 995c5fa3, 99b1bc43, a68b268e, a9f96cdd, b1948b0a, b1fc8b8e, b60334d2, b7cb93ac, ba26e723, bbb1b8b6, bbc9ae5d, bdad9b1f, ca8de6ea, cbded52d, ce22a75a, ce4f8723, cf98881b, d19f7514, d364b489, d47aa2ff, d511f180, d9fac9be, dae9d2b5, e133d23d, e345f17b, e3497940, e98196ab, e9afcf9a, ea9794b1, ed74f2f2, f25ffba3, f2829549, fafffa47.

**Method.** The shape matcher collapses each comp instance to one node, takes the recursive SCCs of the relation graph, and keeps the SCCs whose rules hold a step atom (`compose`, `displacement`, `uniform_delta`, `edge_delta`, `axis_delta`, `jump_delta`) together with a box-as-margins consumer (`BoxCells.box/hole/on_edge`, `Bbox.margin/inside`, `geq`, `gt`). It hit two files: 5c2c9af4 and 4522001f. The wider lists I read in full: 19 recursive cycles holding a step atom, 9 `uniform_delta` lines in 8 files, 32 `compose`/`displacement` rules that read a `margin` or head their own body, 25 `BoxCells` instances, and every `.depth(` / `stride(` readout (a ring family drawn by index rather than by box).

## 1. Callers

1. `programs/solvers/5c2c9af4.dl` — `outline` (lines 46–51) with its `BoxCells<Position>` instance. Seed is the center cell as a degenerate box, `spread` is the inset from the center to the innermost ring, and the run continues from any outline that still draws a grid cell.

No second caller. Every other recursive Position cycle with a step atom closes a Shift over cells or placements, not an Inset over a box: 045e512c `copy`, 08573cc6 `arm`, 16de56c4 `lattice`/`advance`, 1b60fb0c `orbit`, 234bbc79 `slide`, 351d6448 `wave`, 4e34c42c `fitted`/`place`, 5207a7b5 `slant`/`region`, 5ffb2104 and 6ad5bdfd `Settle.room/rest`, 60d73be6 `image`, 7d18a6fb `ink`, 84551f4c `landed`. Every `BoxCells` instance but 5c2c9af4's and 6cbe9eb8's feeds one box per key from `Bbox.margin`, `DrawnRect.rect`, or a single derived box (1a6449f1, 1c786137, 21897d95, 256b0a75, 292dd178, 3dc255db, 444801d8, 446ef5d2, 465b7d93, 4c7dc4dd, 522fdd07, 551d5bf1, 5b526a93, 5daaa586, 68bc2e87, 694f12f3, 6b9890af, 776ffc46, 810b9b61). Every `compose`/`displacement` rule reading a margin translates a box or seats content in a box frame once (11dc524f, 17b866bd, 20981f0e, 21897d95, 2bcee788, 321b1fc6, 34cfa167, 3befdf3e, 3ed85e70, 4938f0c2, 4c177718, 4c5c2cf0, 5b526a93).

## 2. Near-misses

1. 4522001f `fit_box` (line 154) — the spec's rule shape exactly (seed `sq.margin`, recursive `compose` of one delta, clip `geq(M2, ORIGIN)`), but the delta `sq_jump` is a Shift from two `jump_delta`s: the boxes march along the diagonal at constant size. Ruled out by the definition's "one repeated inset"; `grow_box` (line 148) is the same with no recursion.
2. 28e73c20 `walk` (line 55) — closes `params.inset` over the spiral's turn box, one inset per cycle, but the box is the walk's state, read through `nearer`/`same_dist` against the walker; the consumer needs each box paired with the walk step on it, which a `box` set gives no way to read.
3. 6cbe9eb8 `obox` (line 62) — a nest of boxes, each seated so its corner cell lands on the previous shape's anchor, fed to `BoxCells<Color>`. The step is each shape's own extent, and the order comes from `nest` (Order by size), so no single inset generates the run: the "nest that arrives as data" class.
4. 759f3fd3 `Parse.rings` / `ring` (lines 69–78) — square rings around the cross's crossing as a `Dilate` depth under `dir8_elem`. `$Period` (line 105) keeps rings a whole number of the stored period out via `stride`; `$Cycle` walks a color cycle by the ring index. Ruled out by the `Not:` line's `Rim.depth` class — rings drawn as a depth from a set, here Dilate, its outward peer, with unit spacing and no seed box — and by `box` carrying no index, which `$Cycle` reads. The Dilate entry lists this site as its caller.
5. 6df30ad6 `rings` (line 66) — Dilate rings around a non-box shape, read for the first ring holding a dot: rings follow the set's own shape.
6. 5587a8d0 `covers` (line 71) — a `dir8_elem` dilation over Shifts from ORIGIN, run length by `nest.next`: no inset onto a box, and the nest arrives as data.
7. 5751f35e `layer` (line 48) — a Rim depth converted to a box with `uniform_delta` and read by `geq`; no seed, spacing, or closure.
8. One box let out, no closure (`Outset`): 3a301edc `ring_box`, 52fd389e `ring_box`, 543a7ed5 `ring_box`, 58f5dbd5 `crop_box`, 412b6263 `ring`, ed74f2f2 `decompose`.
9. Rings at spacing 1 off the frame or a set's own shape (`Rim.depth`): 13e47133, 3ee1011a, 4290ef0e, 45a5af55, 516b51b7, 522fdd07, 52364a65, 639f5a19, 85c4e7cd.

## 3. Spec

1. Ring index. 759f3fd3 is the one site beyond the surfacing solver that reads a ring family, and it reads it by index: `$Cycle` needs every ring's index, `$Period` the rings at one spacing. With `box` as written, Concentric serves `$Period` alone, and since the ring parse is shared setup, that solver keeps Dilate for both cases. With an index on `box`, one instance (seed = the crossing, unit inset) would serve both cases. That signal comes from a single site that the Dilate entry already claims, so it is a boundary question rather than a change: at a degenerate seed with a unit inset under `dir8`, Concentric-with-index and Dilate are the same relation, and the `Not:` line does not yet name Dilate. On 5c2c9af4 alone the index stays caller-only.
2. Both ways. No site in scope runs a box family both ways.
3. Clip. Unchanged. 4522001f is the one other clipped run and it writes the margin test, but its Shift step rules it out; 759f3fd3 clips by domain (`rings.cell`), as 5c2c9af4 does; 5c2c9af4's partial rings past the grid edge still need "covers a domain cell".

## 4. Reimplementations

Reimplementations: none.

The sites read reach the operation through lib primitives or through proposal comps that have entries (`Dilate` in 759f3fd3 and 6df30ad6, `Settle` in 5ffb2104 and 6ad5bdfd, the `Outset` form in the one-box-let-out class).
