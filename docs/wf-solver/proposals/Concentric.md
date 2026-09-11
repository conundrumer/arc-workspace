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

Survey: 2026-09-10 15:18 — the solvers since 2026-09-09 03:12.

**Method.** The shape matcher collapses each comp instance to one node, takes the recursive SCCs of the relation graph, and keeps the SCCs whose rules hold a step atom (`compose`, `displacement`, `uniform_delta`, `edge_delta`, `axis_delta`, `jump_delta`) together with a box-as-margins consumer (`BoxCells.box/hole/on_edge`, `Bbox.margin/inside`, `geq`, `gt`). It hit two files: 5c2c9af4 and 4522001f. The wider lists I read in full: 19 recursive cycles holding a step atom, 9 `uniform_delta` lines in 8 files, 32 `compose`/`displacement` rules that read a `margin` or head their own body, 25 `BoxCells` instances, and every `.depth(` / `stride(` readout (a ring family drawn by index rather than by box).

## 1. Callers

1. `programs/solvers/5c2c9af4.dl` — `outline` (lines 46–51) with its `BoxCells<Position>` instance. Seed is the center cell as a degenerate box, `spread` is the inset from the center to the innermost ring, and the run continues from any outline that still draws a grid cell.
2. `programs/solvers/8b28cd80.dl` — `ring`/`next_ring` with its `BoxCells<Position>` instance. Seed is the spiral's center cell as a degenerate box, the inset is one cell at every edge, and the run continues from any ring that still draws a grid cell. The recursion carries a color that swaps at each ring, and a seam cell reads the ring inside its own through the step relation — a caller that colors per ring with no index.

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

Survey: 2026-09-11 02:41 — the solvers since 2026-09-10 15:18.

Callers:

8b28cd80 `ring` / `next_ring` (lines 59–64) with its `BoxCells<Position>` instance (lines 66–68). The seed is the spiral's center lattice cell as a degenerate box, `params.ring_step` is one cell at every edge, and `next_ring` lets a ring out by that inset only while the ring still draws a frame cell, so the run ends at the first ring off the grid. The recursion carries the ring's color, swapped at each step through `other`, and the seam rule reads the ring inside a seam cell's ring through `next_ring`.

No second caller. Across the 47 solvers, the shape signature hit one file, 8b28cd80. The only other recursive cycle holding a step atom is 8abad3cf `edge_off`, a near-miss below. The two `uniform_delta` lines are 8b28cd80's `ring_step` and 8719f442's `seat_delta`, a single seat with no closure. The two `compose`/`displacement` rules that read a margin or head their own body are 85b81ff1 `moved` (a box-to-box translation, once) and 8abad3cf `edge_off`. Every other `BoxCells` instance (868de0fa, 890034e9, 8a6d367c, 8cb8642d, 8f215267) is fed one box per key from `DrawnRect.rect` or `Bbox.margin`, and every `geq`/`gt` margin read (846bdb03 `interior`, 84f2aca1 `region`, 8698868d `interior`, 8731374e `covered`, 8a6d367c `crop`, 8f215267 `view`) reads the inside or cover of one box.

Near-misses:

1. 759f3fd3 `Parse.rings` / `ring` (lines 69–76) — square rings around the cross's crossing as a `Dilate` depth under `dir8_elem`; `filled` (line 102) keeps the rings a whole number of the stored period out via `stride`, and `$Cycle` walks a color cycle by the ring index. Ruled out by the `Not:` line's `Rim.depth` class: rings drawn as a depth from a seed set at unit spacing, with no seed box, and read by an index that `box` does not carry. The Dilate entry lists this site as its caller.
2. 8abad3cf `edge_off` (lines 97–103) — a recursion over an `Inset` accumulator that composes each square's side and the gap as `edge_delta`s along `row.next`. The step varies per square and acts on one edge, and no box consumer reads the accumulated offset: it is an offset sum along an order, not a box family under one repeated inset.
3. 8719f442 `seat_delta` (lines 27–28) — a `uniform_delta` used once to seat the block in the tile grid: one inset with no closure over it.
4. 85b81ff1 `moved` (lines 128–134) — `displacement` between two `obj_box.margin` boxes, applied once to move an object's cells: a box translated by a Shift.
5. 8dae5dfc `peel` (lines 34–35) — `Rim.depth` over the objects, read for each layer's depth: rings that follow the set's own shape.
6. 8f215267 `kept` (lines 92–97) — `stride` along one direction inside a frame's box, keeping the I-th dot slot: a 1D spacing on a line, not rings.
7. `BoxCells` over one box per key: 868de0fa `bcells`, 890034e9 `bcells`, 8a6d367c `bcells`, 8cb8642d `bcells`, 8f215267 `bcells`.

Spec:

1. Ring index. 8b28cd80 orders the family: the color alternates per ring, and the seam cell reads the ring one inside its own. With `box` as written, that caller still hand-writes `next_ring` beside the instance to read the inner ring, and carries the color in its own recursion. An ordered readout on the family, a ring index or a `next` between boxes, would let it read the inner ring from the comp and take the color as a cycle walk by index, as 759f3fd3's `$Cycle` does. This scope adds 8b28cd80 to the ordered-readout signal that the 2026-09-10 15:18 survey reported from 759f3fd3 alone; two callers now read the family in order, and neither needs the bare set.
2. Both ways. No site in scope runs a box family both ways.
3. Clip. Unchanged. 8b28cd80 clips by domain: a ring continues from any ring that draws a `frame.cell`, the same test as the surfacing solver. No site in scope writes a margin test against the frame as its clip.

Reimplementations: none.

The sites read reach the operation through lib primitives or through a proposal comp with an entry (`Dilate` in 759f3fd3). Matcher hits: 1 file on the shape signature (recursive SCC holding a step atom and a box-as-margins consumer, comp instances collapsed to one node), 2 recursive cycles holding a step atom, 2 `uniform_delta` lines, 2 `compose`/`displacement` rules reading a margin or self-heading, 6 `BoxCells` instances, 1 `Rim.depth` readout, and 2 `stride` readouts, each read in its rule.
