# `Bbox.gap` — the box cells the set does not fill

A per-key readout on `Bbox`: a grid cell inside the set's bounding box that is not a set cell — the hole a non-solid set leaves in its own box. Existence per key is the solidity test ("fills its box"); the cells themselves are what a solver that paints or individuates the holes reads.

```
// inside Bbox<Key>
.decl gap(key: Key, p: Position)
gap(K, P) :- inside(K, P), !cell(K, P).
```

Not: `BoxCells.hole` (the strict interior of a box given as margins, with no member set); `Rim` (the boundary of the set itself); `Closed` and `Reach` (enclosure against the grid edge); a difference of the box's interior against a set other than the one that fed the box (a bg test, a wall set, another object).

Match: a rule joining a box-interior atom (`Bbox.inside`, `BoxFrame.inside`, or an equivalent local box relation) with the complement of the same key's member set — the set the box bounds. The complement takes several forms: a negated member atom, a color test over the same set, or a box hand-built from the set's occupied lines with no box atom at all. `grep -n 'inside([^)]*), *!' programs/solvers/*.dl` is a starting point only; the shape is matched with the parser.

Survey: 2026-09-08 20:07

The full-corpus pass ran at 2026-09-08 06:47. The pass at the time above covered only the solvers edited since it.

The definition stands as `inside ∧ ¬cell`: no surveyed site wants the gap relative to a different grid, a different key, or an inner frame. The bg reading (box interior against the background color) is a different operation, and the Not line's exclusion of it is load-bearing: `320afe60` carries the two readings as separate cases of one `Choice`, and `44d8ac46` uses each for a different purpose; they coincide only while nothing but the set and the background lies inside the box, which `6d75e8bb`'s `$Each` case breaks.

## Callers

Existence reading — the solidity test. Each site's per-key flag disappears into `!box.gap(K, _)`:

- `22806e14` — `marker`: the one object whose box holds a cell the object misses.
- `264363fd` — `ragged`: the hole-leaving piece is the template, the rest are rectangles.
- `2ba387bc` — `hollow`: a non-solid square stacks in the hole-side column.
- `3345333e` — `gap`: the color that fills its box is the occluder; the complement written as `!in(P, Col)`.
- `6cbe9eb8` — `gap`: a color that fills its box is a block, one that does not is an outline; the complement written as `!in(P, Col)`.
- `320afe60` — `gap(Id, $Own())`: the shape's box holds a cell its substance does not cover.
- `44d8ac46` — `box_gap`: a cell of the hole's box the hole leaves out.
- `470c91de` — `ragged`: the gap minus the box corners; also reads the corner-restricted gap at `:48`.
- `0a1d4ef5` — `hole`: the box hand-built from the set's occupied lines per axis; migration strengthens it, since the line product misses a wholly empty line inside the box.
- `538b439f` — `hole`: a component that leaves a cell of its own box is dust, and only the components that fill their box are reflected.
- `58f5dbd5` — `pierced`: a component that leaves a cell of its own box empty is a key, not a block, and the blocks are the components with no flag.
- `465b7d93` — `edge_hole`: the gap restricted to one edge line of the box, reached through a `BoxCells` fed off `Bbox.margin`. `Bbox.grid` is unfed, so migration has to feed it.
- `7b0280bc` — `gap`: a piece that leaves a cell of its equal-sided box is no square, and a color with such a piece draws the wires.
- `1c786137` — `misdrawn`, first rule: a cell of the color's box edge line the color misses, so the color is not a rectangle outline. Edge-restricted, the complement a color test over the same set, the box reached through a `BoxCells` fed off `Bbox.margin` with `grid` unfed.
- `83302e8f` — `irregular`: a bg component that leaves a cell of its own box is leaky, and the components that fill their box are sealed (`$Solid`).
- `810b9b61` — `edge_gap`: a cell of the ink component's box edge line the component does not draw, so `$Object` leaves it. Edge-restricted, through a `BoxCells` fed off `Bbox.margin` with `grid` unfed; also in `Bbox-edge_gap.md`.

Cell reading — the gap cells are individuated, painted, or measured:

- `42f14c03` — `hole`: fed into `Components<Ident>`, so each hole is a piece-shaped socket.
- `3dc255db` — `cavity.node`: the box interior off the wall, flooded by `Reach`.
- `2bee17df` — `blocked`: a gap cell disqualifies its line.
- `21897d95` — `bracket_host.item`: the bracket's free cells contribute their colors.
- `465b7d93` — `field.cell`: the field the frame encloses, fed into a `Rim` so the interior line against each frame side can be read.
- `3d588dc9` — `notch`: an empty box cell nearer a corner than an occupied one.
- `32597951` — `recolor(P, $Ink())`: the complement written as a color test over the same set.
- `1da012fc` — `comps.node`, first branch: the color-test form again.
- `36fdfd69` — `unmarked`: drops the box key, so it is the union of the gaps only while no cluster's box holds a foreign mark.
- `414297c0` — `dot`: a box-interior cell off the canvas color is the site a glyph stamps at; the complement written as a color test over the same set.
- `52fd389e` — `marker`: a box-interior cell off the body color, tallied into the band's thickness. The color test is set-wide where `gap` is per component, and they agree only while the rectangles stay disjoint, so migration sharpens the rule.
- `58743b76` — `mark`: a canvas cell carrying a mark. The box is built from the background cells, so `!params.bg(Col)` is the color-test form of the complement here, not the bg reading.
- `78e78cff` — `flood.node` (`$Leak`) and `cross.mark` (`$Crosshair`): the box's interior off the frame that fed it, flooded from the seed through `Reach`, or taken on the seed's row or column as ray marks.
- `6e19193c` — `tip`: the empty corner of an arrowhead's box is the tip that casts the diagonal ray. Corner-restricted, read through `inner` for the corner position; the complement is the global ink set, which coincides with the key's set on every input of the task.
- `58490d8a` — `marker`: a cell of the panel's box off the panel color, paired with its position in the panel's own frame.
- `551d5bf1` — `leak.mark`: a border cell the rectangle does not draw, tagged with the side it breaks and cast as a ray. Edge-restricted, and `Bbox.grid` is unfed.
- `68bc2e87` — `under`: a cell of a color's box outline that another color's cell occupies, so that color was drawn later; `Order.before` ranks the colors from it. Edge-restricted, the complement written as another key's set cell (`rect.cell(Col2, P), Col != Col2`), the box reached through a `BoxCells` fed off `Bbox.margin` with `grid` unfed.
- `256b0a75` — `fill`: the color at a frame box's outline cell that the frame color does not draw. Edge-restricted; the complement a color test over the set that fed the box.
- `292dd178` — `cast.mark`: each undrawn outline cell of a wall rectangle casts outward on the side it breaks. Edge-restricted; the complement is the global wall set, which coincides with the key's set on every input of the task.
- `7d18a6fb` — `marker`: a cell of the legend's box the legend color does not cover, paired with its inner position; its color names a shape. The complement written as a color test over the set that fed the box.

Covered but not evidence — crop-complement branches, where a total paint over a box's crop frame pairs the gap branch with a positive branch over the same `inner` cells, so `gap` supplies no join and shortens no rule: `137eaa0f`, `1f85a75f`, `2037f2c7`, `23b5c85d`, `278e5215`, `3a25b0d8`, `48d8fb45`, `50aad11f`.

## Near-misses

- Bg reading — the interior against the background color, not the set that fed the box: `320afe60` `$Joint` (the sibling case of its caller), `6d75e8bb` `filled`, `44d8ac46` `boxed.node`, `358ba94e`, `445eab21`, `37d3e8b2`, `3aa6fb7a`, `271d71e2`, `4e469f39` (also edge-line restricted — `BoxCells.on_edge` territory).
- Difference against another set — a wall, an ink color, another box: `2e65ae53`, `3ed85e70`, `444801d8`, `3490cc26`, `3a301edc`, `42918530`, `52fd389e` `ring` (the let-out box's interior minus the rectangle's own box).
- Different box or domain — a candidate box tested for purity against sets that did not feed it (`31adaf00`, `3eda0437`), the ring/hole split of a margin box (`1c786137`, which is `BoxCells.hole`), and a rule whose domain is not the box's grid cells (`1478ab18`, `414297c0` `outside`, whose domain is the cells the box does not cover).

Survey: 2026-09-09 01:01

The pass read the 48 solvers whose file time is at or after the previous survey's dispatch. Its callers and near-misses are folded into the lists above. It reports no reimplementation of a promoted primitive; the one hand-written relation it flagged, `52df9849`'s `nearer_eq`, is the surfacing site of the `nearer_eq` entry, which records that lib's strict `nearer` cannot serve the non-strict reading.

The definition stands as `inside ∧ ¬cell` at one key. Two findings bear on the entry:

- The `Not:` line's exclusion of the bg reading has to stay stated as "a set other than the one that fed the box". `58743b76` writes the complement as `!params.bg(Col)` — lexically the bg reading, and the gap in fact, because the bg cells are what fed its box — while `543a7ed5`'s `fill_cell(P, $Boxed())` writes the same lexical form and is the bg reading. Which set fed the box decides it, and the atom does not show that.
- Spec question: whether the box-edge-restricted gap deserves a readout of its own. `465b7d93` and `551d5bf1` both want a cell of the box's `d`-side edge line that the set misses — the negative of `Bbox.edge_cell` — and each builds a `BoxCells` instance off `Bbox.margin` to reach `on_edge`. `gap` as written serves both, once they feed `Bbox.grid`; the question is whether the two-instance construction is what the operation should ask of them. The earlier passes saw the same restriction at `470c91de` (corner-restricted) and `4e469f39`.

Further near-misses from this pass: `543a7ed5` `ring` and `5587a8d0` `out`, differences against another box or a dilation; `58c02a16` `pat_cell`, the box interior less two separator lines, which keeps the bg cells the gap excludes; `57edb29d` `mark`, a partition of the set by color over `inner` with `grid` unfed, and `target_cell`, an existence test with the cell unbound; `4938f0c2` `img($Seat())`, a box corner cell with no complement; `54db823b` and `4c7dc4dd`, the box interior with no complement; `5751f35e` `covered`, boxes from a peel depth rather than a member set.

Survey: 2026-09-09 21:19

The pass read the 106 solvers whose file time is at or after the previous survey's dispatch. One new caller, `1c786137` `misdrawn`, added to the list above; the earlier passes listed that file as a near-miss for its separate `BoxCells.hole` site, which stands. `58f5dbd5` and `2bee17df` re-appeared with the operation unchanged. Crop-complement branches: `3a25b0d8` (the gap less the holes) and `5ad4f10b` (the complement as a color test over the set that fed the box) join the covered-but-not-evidence list. No reimplementation.

The definition holds as `inside ∧ ¬cell` at one key. The edge-restricted spec question gains its strongest site: `1c786137` asks whether a color's cells are exactly the edge lines of its own box, so the box's hole is legitimately empty and the whole-box `gap` flags every rectangle outline — `gap` as written cannot serve it even with `grid` fed. Only the edge restriction answers, so the question sharpens to whether `Bbox` should expose the negative of `edge_cell` beside `gap`. That signal rests on `1c786137`, `465b7d93`, and `551d5bf1`, not on the surfacing solver.

Further near-misses, all in the `Not:` classes: `1acc24af`, `5a719d11`, `60b61512`, `4c3d4a41`, `291dc1e1`, `137f0df0`, `604001fa`, `5daaa586`, `5dbc8537`, `1a6449f1`.

Survey: 2026-09-10 01:22

The pass read in full the 36 solvers whose file time is at or after the previous dispatch, and matched the rest of the `since` scope (309 stems) with the parser, reading every hit in its rule. Three edge-restricted cell-reading callers join the list above: `68bc2e87` `under`, and `256b0a75` `fill` and `292dd178` `cast.mark`, which `Bbox-edge_gap.md` already lists. No new whole-box caller: every box instance among the new solvers reads the box positively or partitions the set that fed it by color. One reimplementation, `694f12f3` `interior($Box)`, is `BoxCells.hole` verbatim.

The definition holds as `inside ∧ ¬cell` at one key. No scoped site wants the gap against another grid, key, or frame.

On the edge-restricted spec question: `68bc2e87` `under` is a further site that feeds `Bbox.cell` alone and builds a `BoxCells` off `Bbox.margin` to reach the edge line. `692cd3b6` `door` wants the side-tagged form and reaches the side by instantiating `Rim` over `box.inside` — a third construction for the box's edge line with its outward direction, beside `BoxCells.on_edge` and `edge_cell`'s `d` column. `6cbe9eb8` `inward` (`in(P, Col), !box.edge_cell(Col, P, _)`) is the converse readout, a set cell off the box's edge lines: with `edge_cell`, `gap`, and `edge_gap` it completes the four cells of (edge line | interior) × (set | complement). Its `outline` test (no inward cell: the set lies within the edge lines) mirrors `1c786137`'s `misdrawn` (the edge lines lie within the set); "the set is exactly its box's outline" needs both, and no scoped solver asks for both. The interior-side readout appears at the surfacing solver only.

Further near-misses, by `Not:` class. Bg reading: `692cd3b6` `door` (bg on a box component's outline line, side-tagged through a `Rim` over `box.inside`; coincides with the gap on every input, as at `52fd389e`), `6a1e5592` `notch` (bg inside the wall's box), `67e490f4` `boxed.node` `$Box` (the field color inside the stencil's box). A partition of the set that fed the box by color over `inner`: `25e02866` `paint`, `2faf500b` `moved($Midline)`, `18447a8d` `piece_cell`, `5833af48` `footprint`, `4ff4c9da` `footprint.pattern_member`, `5117e062` `out`. Difference against another set: `21f83797` `out`, `62593bfd` `over`, `6b9890af` `out` (whose `hole` is `BoxCells.hole` of a margin box), `2f0c5170` `out`. Box interior with no complement: `05f2a901` `shape($Extent)`/`blocked($Extent)`, `4a1cacc2` `out`, `694f12f3` `interior($Box)`. Different domain: `42f83767` `legend_cell`. No box: `6c434453` `hole` (`$Flank`). Crop-complement branches: `39a8645d` `out`, `5545f144` `out`, `2f0c5170` `out`.

Survey: 2026-09-10 05:12

The pass read in full the 47 solvers whose file time is at or after the previous dispatch, and matched the whole `since` scope (348 stems) with the parser: a Bbox-family readout joined with a negation or disequality, `geq` with a negation, and every Bbox-family init, plus two matchers for the hand-built box form, which found none. Two cell-reading callers join the list above, `78e78cff` and `6e19193c`. Crop-complement branch: `6ecd11f4` `out`. No reimplementation.

The definition holds as `inside ∧ ¬cell` at one key. `78e78cff` is the cleanest whole-box cell-reading site: the box is fed by exactly the set the complement negates, `grid` is fed, and both cases read the same relation. `6e19193c` repeats the corner restriction (`470c91de`) and the gap cell paired with its inner position (`58490d8a`), and adds no interface pressure: `gap(Id, P), box.inner(Id, P, P_inner)` is the natural form, since `gap` carries no inner position. The edge-restricted spec question gains no site.

Further near-misses, by `Not:` class. Partition of the set that fed the box by color over `inner`: `78332cb0` `port`. Difference against another set: `79369cc6` `occ.shape`, `7837ac64` `out`. Different domain: `6ffbe589` `turns.item`, `776ffc46` `loose.node`. Box interior or edge with no complement: `212895b5` `seed`/`diag_arm`, `6e4f6532` `obj_box.edge_cell`, `762cd429` `seed.corner`/`edge_min`, `7447852a` `pocket_box.edge_min`, `6f473927` `box.margin`, and the crops `72ca375d`, `73ccf9c2`, `7491f3cf`. No box: `6e453dd6` `gap`, `7acdf6d3` `hollow.between`, `71e489b6` `hole`.

Survey: 2026-09-10 07:51

The pass read in full the 37 solvers whose file time is at or after the previous dispatch, and matched the whole `since` scope (382 stems) with the parser: a Bbox-family readout or `geq`/`gt` joined with a negation or disequality, every Bbox-family init, and two hand-built box matchers, which found no box. Two callers join the lists above: `810b9b61` `edge_gap` (existence, edge-restricted) and `7d18a6fb` `marker` (cell reading, whole box). The surfacing solver `83302e8f` `irregular` is `inside ∧ ¬cell` at one key with `grid` fed. `7b0280bc` `gap` and `264363fd` `ragged` re-appeared unchanged.

The definition holds as `inside ∧ ¬cell` at one key. The whole-box sites of the pass feed `grid` and negate exactly the set that fed the box; `7d18a6fb` repeats the inner-position pairing of `58490d8a` and `6e19193c`, and `gap(K, P), box.inner(K, P, P_inner)` stays the natural form. The edge-restricted spec question gains `810b9b61`, the fifth site that builds a `BoxCells` off `Bbox.margin` to reach `on_edge`. `7ee1c6ea` `inside($Box)` states the `BoxCells.hole` reading over a `Bbox` in one lib atom, `gt(P, margin)`, with no second instance; the gap and the hole coincide there only because the frame is an outline.

Further near-misses, by `Not:` class. Bg reading: `7d1f7ee8` `enclosed($Rect)`, `7ee1c6ea` `ink($Held)`. Partition of the set that fed the box by color over `inner`: `7c9b52a0` `ink`, `7c008303` `out`, `2a5f8217` `same.pattern_member`/`observed_member`, `6350f1f4` `out($Expand)`/`out($Invert)`. Difference against another set: `7df24a62` `filled` (also a different domain), `446ef5d2` `spills` (edge-restricted). Different domain: `7d7772cc` `free_cell`, `7d18a6fb` `shape.cell`, `22233c11` `echo_cell`. Box read positively with no complement: `7d7772cc` `open_dir`/`rest`, `817e6c09` `block_dist`, `7c66cb00` `fall`, `7d419a02` `unit.extent`, `342ae2ed` `link`, `40f6cd08` `nested`, `7d1f7ee8` `nested_rect`, `2697da3f`, `34cfa167`, `3befdf3e`, and the crops `7bb29440`, `7e576d6e` `gap_mid`, `80af3007`, `83b6b474` `occ.shape`, `7b3084d4` `image`. No box: `689c358e` `cross_cell`, `6a980be1` `strip_in`, `83b6b474` `border`, `d9fac9be` `gap`/`defect`.

Reimplementation: `7e576d6e` `broken`/`divider`/`on_divider` hand-write `DividerFrame.on_divider`.

Survey: 2026-09-10 08:05

The pass read in full the 9 solvers whose file time is at or after the previous dispatch, and matched the whole `since` scope (382 stems, the previous dispatch's scope) with the parser: the same hit set, shifted by line number in two files. No new caller: the surfacing solver `83302e8f` `irregular` is the only box readout joined with a negation among the nine, unchanged. No reimplementation: `7e576d6e` now instantiates `DividerFrame<Unit>`.

The definition holds as `inside ∧ ¬cell` at one key. The edge-restricted spec question gains no site: `56dc2b01` `back_line` reads `Bbox.edge_cell` positively on the resting mover's trailing face, with `grid` unfed.

Further near-misses, by `Not:` class. Box read positively with no complement: `56dc2b01` `back_line`. Crops: `7e576d6e` `gap_mid`, `83b6b474` `occ.shape`. No box: `7e576d6e` `gap` (a divider cell off the divider's mode color), `83b6b474` `border`.
