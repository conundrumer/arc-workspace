# `Concat2D<Key>` — the frame two cell sets assemble as tile index × intile position

The 2D frame that an outer cell set and an inner cell set assemble, per key: one frame cell per (outer, inner) pair, recomposed through `concat_2d`. It is the assembling peer of `Divide2D` and `Tile2D`, which decompose a frame that already exists; here the frame is built, and its extent is a correspondence over the two sets, so a solver derives no number for it. The two sets are inputs, so the self-product (the input tiled by itself, as in 007bbfb7) and the scale-up (an input cell set times a stored intile frame, as in 2072aba6) are the same instance.

```
.comp Concat2D<Key> {
    // The tile indices, per key.
    .decl outer(key: Key, p: Position)  // input

    // The within-tile positions, per key.
    .decl inner(key: Key, p: Position)  // input

    // The gap between tiles — the instance's input, unkeyed.
    .decl gap(g: number)  // input

    // A frame cell beside the tile index and intile position it recomposes.
    .decl cell(key: Key, p: Position, p_outer: Position, p_inner: Position)
    cell(K, P, P_outer, P_inner) :-
        outer(K, P_outer), inner(K, P_inner), gap(G),
        concat_2d(P_outer, P_inner, G, P).
}
```

Solver-local form (8f2ea7aa, under `$Crop`; 007bbfb7 writes it over `in` for both sets):

```
cell(P_grid_out, P_tile, P_intile, $Crop()) :-
    shape(P_tile, _, $Crop()), shape(P_intile, _, $Crop()),
    concat_2d(P_tile, P_intile, 0, P_grid_out).
```

Not: `Divide2D` and `Tile2D`, which read the tile index and intile position off a frame the input already has; `concat_2d` in a rule whose outer or inner position is bound by a correspondence rather than a cell set (a divide, an `apply` image, a position table with a payload the rule reads, as `params.tile_d4`), which states where a cell lands, not a frame — a per-outer inner set, each tile taking the content its color, marker, or object names, is the keyed instance, not an exclusion; the 1D `concat` and `concat_slab` forms; `ConcatPipeline`, whose tiles differ in size.

Match: a rule with a `concat_2d` atom whose outer and inner positions are each bound by a positive atom over a cell set — `in`, a `Params` frame relation, a `BoxFrame` or `Reframe` inner read, or a plain solver relation — and whose grid position is the rule's head position or feeds it. The two binding atoms may be one relation twice (the self-product) or two relations. Grep `concat_2d(`; match the binding shape with the parser (`tests/test_ast_match.py`).

Survey: 2026-09-11 02:07 — the whole corpus.

Callers:
007bbfb7 cell — the self-product `in` × `in`, the output frame as tile index × intile cell.
0692e18c cell — the self-product `in` × `in`.
ad7e01d0 cell (family with cce03e0d) — the self-product `in` × `in`.
8e2edd66 out_cell, ink_at — `in` × `in` for the output frame, and `bg_cell` × `bg_cell` for the inked cells.
27f8ce4f out — `in` × `in`, with the tile's color read on the outer cell in the same rule.
5b6cbef5 out — `in` × `in` in two rules, split by whether the outer cell is bg.
973e499e out — `in` × `in` in two rules, split by whether the two cells share a color.
ccd554ac out — `in` × `in`.
15696249 out — `in` × `in`, with a gate per tile.
48f8583b out — `in` × `in`, with an active set per tile.
80af3007 cell — `pixel` × `pixel`, the scaled-down shape times itself.
8f2ea7aa cell — `shape` × `shape` under `$Crop`, the surfacing site.
2072aba6 cell — `in` × `params.intile`, the stored intile frame; `Determine.template` repeats the product over `ex_in`.
60c09cac out (family with 9172f3a0, c59eb873) — `in` × `params.intile`.
469497ad scaled — `in` × `intile.cell`, a `Frame2D` sized by the palette count.
ac0a08a4 out — `in` × `block.cell`, a `Frame2D` keyed by `Choice`.
d4b1c2b1 out — `in` × `block.cell`.
8a004b2b drawing — `blueprint.inner` (a `BoxFrame` inner read) × `tile.cell`.
898e7135 out, congruent.observed_member — `board_box.inner` × `block.cell` for the output, and `hole_box.inner` × `block.cell` feeding `apply` for the fit test, both keyed by the scale.
46f33fce out — `render` (the input recolored per case) × `subf.cell`, keyed by `Choice`.
1be83260 assembled — `palette` × `body` with `params.gap`, the template body laid out per palette cell.
6165ea8f painted — `tile_color` × `entry.cell` with `params.gap`.
10fcaaa3 Parse.tiled — `arrangement.cell` × `grid(K, ...)`, keyed.
310f3251 out — `arr.cell` × `tile_content`.
48131b3c out — `arrangement.cell` × `swapped`.
a59b95c0 out — `arr.cell` × `in`.
91413438 out — `tiles.cell` × `in`, with a copy set per tile.
3979b1a8 tile_cell — `tiles.cell` × `in`; `Determine.tile_mismatch` repeats the product over `ex_in`, its grid position feeding a negated `ex_out` test rather than the head.
539a4f51 frame_cell — `tiles.cell` × `in` under `$Scale`.
f5b8619d out — `params.tile` × `repainted`.
412b6263 placed — `layout.cell` × `content` with `params.line_width` as the gap, under `$Layout`.
2ba387bc out — `tiles.cell` × `cells.cell`, the classified squares laid out.
65b59efc out — `marker_cell` × `template_cell`.
8719f442 cell — the seat tile and its Dir8 ring (stated inline through `neighbor`) × `in`; the outer set would become a relation.
0bb8deee out ($Concat) — `box.inner` keyed by the tile position: the outer position is the key and the inner set is that tile's crop box.
7d18a6fb ink ($Concat) — `quadrant_ink`, which is `quadrant_color` × `shape.inner` keyed by the marker color, with `params.gap`.
42f83767 out — `composition.inner` × `stencil_cell`, the stencil chosen per tile through `legend_color`; keyed by the legend block, the outer set per key is the tiles of that block's color.
58f5dbd5 view ($Arrange) — `tile.pos` × `block_box.inner` keyed by block color, with `params.border` as the gap; the outer set per key is one tile.
57aa92db seat, stamp — `shape_cell` × `block.inner` keyed by object, the scaled shape whose grid position then feeds `displacement` and `compose`.

Near-misses:
The unfold family's table case — 00576224 out ($Lookup), 67e8384a out ($Lookup) with 0c786b71, 3af2c5a8, 62c24649, 833dafe3, 4c4377d9 out ($Lookup) with 59341089, 6d0aefbc, 6fa7a44f, 8be77c9e, bc4146bd, c9e6f938, 46442a0e out ($Lookup), 7953d61e out, 7fe24cdd out ($Table), 8d5021e8 out ($Lookup), c48954c1 out ($Lookup), 47c1f68c paint ($Lookup): the outer is bound by `params.tile_d4`, a stored tile-position table, and the inner by `apply`, the D4 image of an input cell; the rule states where an input cell lands, a correspondence, which the Not line excludes.
The mirror case — 67e8384a out ($Mirror) with 0c786b71, 3af2c5a8, 62c24649, 833dafe3, 8d5021e8, c48954c1, and 47c1f68c paint ($Mirror): both positions come from `mirror`, a per-tile reflection correspondence.
The unfold case — 67e8384a out ($Unfold) with its family, 4c4377d9 out ($Unfold) with its family, 8d5021e8, c48954c1, and 47c1f68c paint ($Unfold): the tile and intile positions arrive bound together by `unfold_val` or `unfold`, a recursive correspondence that carries content across tile edges; no cell set binds either position.
00576224 out ($Alt, $Mid), 46442a0e out ($Rot), 7fe24cdd out ($Spin), 760b3cac mirror: at least one position is an `apply` image, a correspondence.
47c1f68c cell: both positions come from `divide_2d`, excluded as a divide.
8ee62060 out: the inner comes from `divide_by_size_2d` and the outer from `apply`.
8b28cd80 lattice: the inner is the literal `ORIGIN`, so the rule scales input cells by the gap and assembles no inner set.
The 1D forms — 12997ef3, 28bf18c6, 291dc1e1, 2d0172a1, 412b6263 (its `$Stack` rule), 4852f2fa, 50aad11f, 652646ff, 6f473927, 78332cb0, 833966f4, 85b81ff1, 963e52fc, a416b8f3, eb281b96, f25ffba3: `concat` and `concat_slab`, excluded as the 1D forms. No solver composes two 1D concats into the 2D frame.

Spec:
The interface holds as written for the plain product sites, and the gap input earns its place: 1be83260, 6165ea8f, 412b6263, 7d18a6fb, and 58f5dbd5 pass a nonzero gap. Two readings should go into the entry. First, five callers (0bb8deee, 7d18a6fb, 42f83767, 58f5dbd5, 57aa92db) assemble crops whose inner set depends on the outer position: each tile takes the content its color, marker, or object names. They fit the comp keyed by that content's id, with `outer(K, ·)` the tiles that take content K and `inner(K, ·)` that content's frame; in 0bb8deee the key is the outer position itself. The Not line's "a stored tile position (a lookup)" reads as excluding these, so the entry should say that a per-outer inner set is the keyed instance, and reserve the exclusion for a position table with a payload the rule reads, as `params.tile_d4` is. Second, the largest hit class, the unfold family's table case, is the same frame (the key set of `params.tile_d4` × `in`) with a D4 read after; the entry excludes it as a correspondence, and that exclusion stands, since the comp's cell would add atoms to those rules and remove none. Two Determine sites (2072aba6, 3979b1a8) repeat the program's product over `ex_in`; a lib comp instantiated in Determine keyed by `Example` covers them without an interface change.

Reimplementations: none.
Matcher: 100 `concat_2d` sites across 63 solvers, found by grep and read through the parser, which bound each site's outer and inner argument to the positive atoms of its rule and reported the head and the grid position's use; the 1D forms were read from a grep of `concat(` and `concat_slab(`.
