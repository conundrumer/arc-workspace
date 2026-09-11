# Box — the edge-margin record and its readings

Every spatial value in lib is one record of four integers, one per frame edge. Today it is named Position, with Shift and Inset as aliases and the rectangle reading undeclared. This change grounds the record in its algebra, names the record and its two special subsets, states the operations as that algebra's operations, and retires the comps whose whole work is a pointwise read.

## Foundation

A frame has extent F = (H, W). A record (t, b, l, r) names the rectangle whose rows run from t to H − 1 − b and whose columns run from l to W − 1 − r: a rectangle placed in a frame by its margins from the four edges. A margin may be negative, and the rectangle then reaches past the frame. The records form the group Z⁴ under componentwise addition, and every spatial operation in lib is one of four things: the group operations, the pointwise order, the projections onto components, and the D4 action.

```
.type Box      = [t: number, b: number, l: number, r: number]
.type Position = Box  // a cell: extent 1 on both axes, so the frame's extent is readable from it
.type Offset   = Box  // a translation: the two margins cancel on each axis
```

Souffle equivalence types are interchangeable, so the two aliases document a column's reading and check nothing.

The per-axis sum s(x) = (t + b, l + r) is a homomorphism onto Z². It measures the frame's extent minus the rectangle's, so boxes with one sum are translates of one another. The two subsets the aliases name are the two that the algebra singles out:

- A cell has s(x) = F − 1: the coset of extent-1 boxes. A Position carries its frame, which no other box does.
- A translation has s(x) = 0: the kernel. Adding an Offset to any box moves it and keeps its extent.

Every other reading, a rectangle, a margin, an inset, a change per edge, is a Box read against a frame the reader supplies. The retired Inset columns bear this out: five of the eight hold a rectangle, and the sixth is a per-edge change composed onto a cell to make a rectangle.

The operations, as the algebra gives them:

- **Addition composes framings.** For a box A in the frame and a box B in A's own frame, A + B is B in the outer frame. A cell seated in a box, a box moved by an offset, a frame inset by a margin: one operation.
- **Subtraction is relative position.** B − A is B in A's frame. A cell minus a box is the cell in the box's coordinates. One cell minus another of the same frame is the offset between them.
- **The pointwise order is nesting.** A ≥ B pointwise iff A lies inside B: larger margins, smaller rectangle. A cell inside a box is the extent-1 case. Strict > is the interior: inside, and touching no side.
- **Coverage is nonnegativity of the relative position.** p inside B iff p − B ≥ 0: the relative cell lies on the box's own frame.
- **The zero box.** As a box the zero record is the whole frame, and as an offset it is no move. `inside(B, ZERO)` is a box on the frame; `interior(P, ZERO)` is a cell off the border.
- **The bounding box is the pointwise minimum** over a set, and the intersection of two boxes is their pointwise maximum. `Bbox` is the minimum, per key.
- **An axis-only record is a band.** With the other axis zero, it is the whole row or column through a cell. `split` gives a cell's two bands, and their sum is the cell.
- **The D4 action permutes the components**, so it preserves addition, the order, and the sums up to an axis swap. Every operation above is equivariant.

**Typing rule.** A primitive types a column `Box` unless it reads the frame's extent from the value, which assumes a cell: the `axis_dim` and `divide` families, and the cell inputs of comps keep `Position`. A column holds `Offset` when its value is a translation by construction: `jump_offset`, `step_offset`, `OffsetInvariance.cand`, `Components.step`.

## Primitives

The inline relations, with the names that the readings give them:

```
// Addition: b in a's frame, seated in the outer frame. A cell seated in a
// box, a box moved by an offset, a frame inset by a margin.
.decl compose(a: Box, b: Box, c: Box) inline

// Subtraction: x relative to base. A cell in a box's coordinates, or the
// offset between two cells of one frame.
.decl relative(base: Box, x: Box, x_rel: Box) inline

// Pointwise ≥: a inside b. A cell inside a box is the extent-1 case; at
// b = ZERO, a lies on the frame.
.decl inside(a: Box, b: Box) inline

// Pointwise >: a in the interior of b, touching no side. At b = ZERO,
// off the frame's border.
.decl interior(a: Box, b: Box) inline

// Cell p of box b, as a cell of b's own frame.
.decl crop(p: Position, b: Box, p_rel: Position) inline
crop(P, B, P_rel) :- inside(P, B), relative(B, P, P_rel).

// Cell p on box b's d-side edge.
.decl box_edge(p: Position, b: Box, d: Dir) inline
box_edge(P, B, D) :- inside(P, B), dir_elem(D), same_dist(D, P, B).

// Cell p at box b's corner d.
.decl box_corner(p: Position, b: Box, d: DiagDir) inline
box_corner(P, B, D) :- inside(P, B), corner_anchor(D, P, B).

// Extent of box b along a, in the frame of cell p.
.decl box_extent(b: Box, p: Position, a: Axis, n: number) inline

// Boxes inset from the frame: by k on side d; by k1 on side d and k2 on its
// opposite; by k on every side.
.decl edge_inset(d: Dir8, k: number, b: Box) inline
.decl axis_inset(d: Dir, k1: number, k2: number, b: Box) inline
.decl uniform_inset(k: number, b: Box) inline

// Translations: k cells toward d; one cell toward d.
.decl jump_offset(d: Dir8, k: number, v: Offset) inline
.decl step_offset(d: Dir8, v: Offset) inline
```

The cell comes first in every box read, as in `inside` and `interior`. `crop` carries the coverage test: it is the content of a box in the box's coordinates, and a cell outside the box is `relative` alone, as the seat sites write it. An inline runs one way, so the seat of a relative cell back in the grid is `compose(B, P_rel, P)`, and the site states its own domain test on P.

A defect site cannot negate an inline whose clause introduces variables; it wraps a local relation over its own domain, the existing idiom. Negation is a property of the site, not of the operation, so it earns no comp readout.

## Comps

The criterion: a comp earns its keyed-input machinery only where a derivation forces materialization — an aggregate, a recursion, a gather of several rows into one value. A pointwise read is an inline.

Remain:

- `Bbox` — the pointwise minimum over `cell`, an aggregate. Its one readout is `box(key, b: Box)`. `edge_min` is `dist` on the box, `inside` is `inside` over the caller's own domain, `edge_cell` and `corner` are `box_edge` and `box_corner` over the set, `extent` and `extents` are `box_extent`, and `grid` fed only `inside`; all retire. An instance named `box` renames in the same pass, so no site reads `box.box`.
- `DirPack` — gathers four Dir-keyed rows into one value. Readout `box(key, b: Box)`; the caller's column names the reading. `Dir` states the key of its input rows, as in `DirFrame`. A caller with an edge of no width writes that edge's zero row: zero is absence, and the program may write 0.
- `DrawnRect` → `Outlines` — recursion over runs. Readout `rect(key, b)` → `box(key, b: Box)`.

Retire into the inlines:

- `BoxCells` — `on_edge` is `box_edge`; `hole` is `interior`.
- `BoxFrame` — `Bbox` plus `crop`.
- `MarginFrame` — an inset constructor, or `DirPack`, plus `crop`.
- `Reframe` — `view` is `relative`; the Occurrences internals write it in their own rules.

Names that follow: `ShiftInvariance` → `OffsetInvariance`, named for its value type as `D4Map` is; `DividerFrame` → `DividerTiles`, since its output is a tile arrangement, the family of `Divide2D` and `Tile2D`.

## The matrix

Each box unit is a move between three representations; after the change, the composite moves are conjunctions instead of comps.

| have \ want    | box       | inner view          | edge/hole split                  |
| -------------- | --------- | ------------------- | -------------------------------- |
| cell set       | `Bbox`    | `Bbox` + `crop`     | `Bbox` + `box_edge` / `interior` |
| per-edge rows  | `DirPack` | `DirPack` + `crop`  | `DirPack` + inlines              |
| box            | —         | `crop`              | `box_edge`, `inside`, `interior` |

`Outlines` stands outside the matrix as the one detector — cell set to many boxes — feeding the box row.

## Caller shape, before and after

A keyed split site:

```
.init bcells = BoxCells<Ident>
bcells.box(Id, B) :- bbox.margin(Id, B).
bcells.cell(Id, P) :- bbox.margin(Id, _), in(P, _).
paint(Id, P) :- bcells.on_edge(Id, P, _).
```

becomes one atom with the caller's own key:

```
paint(Id, P) :- bbox.box(Id, B), in(P, _), box_edge(P, B, _).
```

A crop site (`BoxFrame` today) becomes `Bbox` plus the inner read:

```
out(P_rel, Col) :- bbox.box(K, B), in(P, Col), crop(P, B, P_rel).
```

## Names

The names are the geometric vocabulary, the corpus's own register, throughout: `Box`, `Position`, `Offset`; `ZERO` for the zero box, since "origin" names a point and the record is the whole frame; `compose` and `relative`; `inside` and `interior`; `crop`; `box_edge`, `box_corner`, `box_extent`; the inset and offset constructors; `Bbox`, `DirPack`, `Outlines`, `OffsetInvariance`. Every box readout is `box`. A local relation that takes one of these names renames.

The word "frame" carries two senses today: the coordinate frame a Position is relative to (style.md's Position frames — grid, tile, intile — and prose like "the box's own frame"), and the realized-cells sense in comp names (`DirFrame`, `AxisFrame`, `Frame2D`, `OrderFrame`, `frame_pos`) — with `MarginFrame` and `BoxFrame` until now carrying a third meaning, an inner view. Retiring those two purges the third sense, and this change adopts the result as a rule: **Frame in a unit name means a frame of cells realized or induced from data; the coordinate-frame sense lives in prose and in Position column names.** The rule keeps `DirFrame`, `AxisFrame`, `Frame2D`, and `OrderFrame`: each realizes a frame from indices, an extent, per-axis extents, or an ordered member set, and `DirFrame` against `AxisFrame` states the directed/undirected distinction that a source-data rubric (`IndexFrame`, `ExtentFrame`) would bury.

## Surface

lib.dl: the header comment, which carries the Foundation; the type block; `ORIGIN` → `ZERO`; the retyped signatures under the typing rule; the renamed and new inlines; the comps named above; every doc comment saying Shift or Inset. docs/wf-solver: principles.md, where the Foundation's readings back Relational form and ARC types; style.md's Position-frames section — for the reading comment, the frame rule, the `crop` intile reading, the program-literal rule (every lib constant macro but `ZERO`), and a variable rule by reading (`B` for a Box, `V` for an Offset, `P_rel` for a relative cell; `M` retires as a box name); patterns.md's "Boxes as margin Positions" entry, whose content becomes the Box type's own comment, and its type-directed closure line naming Shift and Inset; tests/test_context.py, which asserts that entry's index line. Solvers: those writing `ORIGIN`, those typing a parameter Shift or Inset, those initing a retiring comp, the detector, or `ShiftInvariance`, those calling `displacement`, `geq`, `gt`, `jump_delta`, `step_delta`, or an inset constructor, those reading a Bbox's `margin`, `edge_min`, `inside`, `edge_cell`, `corner`, `extent`, or `extents`, and those declaring a local `inside` or `interior`.

Related entries: `Bbox-gap.md` (open) states its code form on `Bbox.inside` and its `Not:` line on `BoxCells.hole`; `Bbox-corner_cell.md` (closed) rests on the one-atom `!corner` and on `inner` plus `corner_dist`. Both are re-read against this change.

Not: `Dim` (the frame's extent, ParamsHelpers grouping notation); `Rim` and `Components` (cell-set units holding no box value); graph edges (`Order.before`, `CycleWalk.succ`).

Match: every `ORIGIN`; every `Shift` or `Inset` in a type position; every `.init` of `BoxCells`, `BoxFrame`, `MarginFrame`, `Reframe`, `DrawnRect`, `ShiftInvariance`; every `jump_delta`, `step_delta`, `edge_delta`, `axis_delta`, `uniform_delta`, `displacement`, `geq`, or `gt` call; every `.margin(`, `.edge_min(`, `.inside(`, `.edge_cell(`, `.corner(`, `.extent(`, or `.extents(` read on a `Bbox` instance; every parameter whose Position is read as margins; every solver-local relation restating `box_edge` or `crop`.

Survey: 2026-09-08 19:32

The scope was the whole corpus: 540 solvers, 495 families. The Match clauses together reach 195 files, 190 families. The numbers below are files.

## Callers

`crop`, the inner view:

- `BoxFrame` sites: 130, with 241 `inner` reads. Every init reads `inner`. 56 feed `grid` (a crop); the rest feed `cell` only, where the box is the set's own hull and the covering test is vacuous. Representatives: `2013d3e2` `crop` (a crop, and the file already owns the name), `0607ce86` `copy_color`/`out` (each cell of a panel in the panel's frame), `4df5b0ae` `line`/`paint` (a shape cell in its box, reseated by rank), `48634b99` `bar_idx`.
- `MarginFrame` sites: 9. Eight feed `width` from one scalar per edge, or per one edge, so a delta constructor states the box in one atom: `uniform_delta` at `33067df9`, `332efdb3`, `4e45f183`, `4e7e0eb9`, `f8b3ba0a`, `77fdfe62`; `edge_delta` at `6d1d5c90`, `bd4472b8`. `4522001f` `sq` feeds four rotated per-edge scalars and keeps `DirPack`.
- `Reframe` with a box outer: 5. `1990f7a8` `rel`, `20270e3b` `socket_rel`, `3befdf3e` `fig_rf`, `17b866bd` `view`, `48d8fb45` `win`.

The seat, `displacement` or `compose` against a box with no covering test: 20 files write it inline (`0bb8deee` `out`, `11dc524f` `home`, `16b78196` `seat_step`, `2bcee788` `mirror`, `4938f0c2` `img`, `4c5c2cf0` `copy`/`orbit`, `0934a4d8` `mosaic`, `412b6263` `placed`, `49d1d64f` `seated`, `2b9ef948` `moved_box`, `4522001f` `grow_box`/`fit_box`, and others). Their third column is the relative position, and the sites name it so (`Delta`, `Sh`, `P_rel`). They are callers of `relative`, not of `crop`.

`box_edge`, a covered cell on a box's edge line:

- `BoxCells` sites: 18, with 15 `on_edge` and 17 `hole` reads. `on_edge` is `geq` plus `same_dist` verbatim, and `hole` is `gt`, so the retirement is exact. `14b8e18c`, `1a6449f1`, `1c786137`, `21897d95`, `256b0a75`, `292dd178`, `2d0172a1`, `3de23699`, `3dc255db`, `4347f46a`, `444801d8`, `446ef5d2`, `465b7d93`, `4c7dc4dd`, `50cb2852`, `522fdd07`, `551d5bf1`, `bb43febb`.
- Hand-written through `inner` and `dist(_, D, 0)`: 5. `15660dd6` `ring_pos`, `212895b5` `Parse.seed`, `42918530` `outline`, `4290ef0e`, `4e469f39`. The closed entry `Bbox-corner_cell.md` named this operation as the edge form with the wider caller base.

`Outlines`: 3. `1a6449f1`, `1c786137`, `4c7dc4dd`. All three feed `rect` into a `BoxCells` box and read `hole`.

The readings:

- `Shift` or `Inset` in a type position: 63 files, 155 `Shift` columns and 19 `Inset` columns in 8 files.
- A stored Box typed `Position`, read by `geq` directly: `4c3d4a41` `params.box`. Solver-local Box relations typed `Position`: 13 files, among them `2b9ef948` `box`, `3eda0437` `box_ink`, `40f6cd08` `nested`.
- Of the 8 `Inset` files, five hold a Box: `0934a4d8` `mosaic_margin`, `412b6263` `ring`, `49d1d64f` `seat_delta`, `2697da3f` `arm_margin`, `28e73c20` `walk`'s third column, whose comment reads "the margin ahead of it". `48d8fb45` `win_delta` is a per-edge change composed onto a cell to make a box. At `412b6263`, `49d1d64f`, and `28e73c20`, `uniform_delta`'s output is the Box.

## Near-misses

- `2bcee788` `wall.cell`: `same_dist` against a box, wanting the whole line across the grid. `box_edge`'s `geq` cuts it to the edge segment, so `same_dist` stays.
- `same_dist` against a cell, 9 files: no box in the rule.
- `Reframe` with an anchor-cell outer, 9 of its 13 callers (`03560426`, `137eaa0f`, `247ef758`, `3345333e`, `47996f11`, `981571dc`, `90347967`, `e729b7be`, `212895b5`): the third column is consumed as an Offset, so the read is `displacement`.
- Box-to-box `displacement`, 3 files (`321b1fc6`, `34cfa167`, `3ed85e70`): an Offset between boxes, not an inner view.
- `Bbox.edge_cell` readers, 3 files: member-only, where `box_edge` ranges over covered cells.
- `dist(P, D, 0)` as the frame border: `box_edge(P, ORIGIN, D)` would be an indirection past a one-atom form.
- `Dim`: no solver column carries it; 67 files pass it as a literal to `ParamsHelpers`.

## Spec

- `crop` with the covering test serves the 144 view sites, and the 20 seat sites are `displacement`. Without the test, the third column is an Offset, and the crop sites add `geq` back.
- Negation: `3de23699` `escapes` negates `hole`, the strict interior, and `103eff5b`, `414297c0`, `15660dd6` negate `inside` or `viewed`. Each wraps a local relation.
- Two closed entries rest on retiring comps. `Border.md` closed into `MarginFrame` to avoid a packed construction; six of the ten `MarginFrame` sites are its callers, and they return to `uniform_delta` plus `crop`, which the Box type makes principled. `Bbox-corner_cell.md` closed on `inner` plus `corner_dist`; its four callers (`470c91de`, `4938f0c2`, `1478ab18`, `4c416de3`) take `box_corner`.
- `apply_about.md`, open, composes `displacement`, `apply`, and `compose`; ten of its callers are seat sites above. Two of them (`47996f11`, `981571dc`) store a frame origin `center([1, -1, 1, -1])` whose per-axis sums cancel, an Offset by the typing rule while used as a base. In the algebra a base need not be a cell: `relative` and `compose` take any Box.

## Addendum: the Bbox readouts and the renames

Snapshot 2026-09-08 19:57, 541 files. The whole change reaches 238 files, 233 families.

Reads of `inside`, `edge_cell`, and `corner`: 120 sites in 76 files, 31 of them new to the change.

- `inside`: 79 sites, 49 files. The dominant use is a grid cell covered by the box, feeding a paint rule or a domain. 27 instances feed `grid` through a rule whose only other content is a key-binding guard, and those rules disappear, since the caller's rule binds the key from the box. 6 instances read a domain other than the input grid (`21897d95`, `33067df9`, `37d3e8b2`, `40f6cd08`, `44d8ac46`, `4c7dc4dd`), and the replacement uses that domain.
- `edge_cell`: 20 sites, 17 files, read as a set cell on the box's d-side, mostly feeding a cast or a tally. `corner`: 21 sites, 14 files, the same at a corner. Both reproduce exactly as the set's cells beside `box_edge` or `corner_anchor`.
- Negated reads, each needing a local wrapper: 15 in 12 files (`137f0df0`, `1da012fc`, `1e81d6f9`, `21f83797`, `256b0a75`, `3a301edc` ×3 over two instances, `3ed85e70`, `4a1cacc2`, `52fd389e` on `inside`; `1e5d6875` ×2 and `21897d95` on `corner`; `4c3d4a41` on `edge_cell`). With the four negations of retiring comps' readouts (`103eff5b`, `414297c0`, `15660dd6`, `3de23699`), 18 wrappers in 15 files. No read sits in an aggregator; the corpus holds no aggregate outside lib.
- Instances named `box`: 114 of 287, carrying 70 of the 120 reads and 112 of the 241 `inner` reads.

`ShiftInvariance`: 12 files, 16 inits, every `delta` column a translation. `jump_delta`: 18 files; `step_delta`: 12 files; every output a translation, none landing in an `Inset` column.

Near-misses: `params.corner` (a stored DiagDir, 20 files) and the `corner` inputs of `LexOrder` and `Diagonal` match the grep and not the operation; `20a9e565` `slot` reads `edge_min` against a line of a 1D frame, not a set cell.

Witnessed readings beyond the cell case: `geq(Box, ORIGIN)` at `16b78196`, `20981f0e`, `4522001f`; `geq(Box, Box)` nesting at `40f6cd08`; a box let out by a uniform inset, through `displacement`, at `52fd389e`.

Survey: 2026-09-10 15:01 — the solvers since 2026-09-08 19:32.

# Survey: Box — scope of 438 solvers (2026-09-10)

The scope is the working tree's solver set: 404 of the 438 carry uncommitted edits, and 49 were committed after the entry's 2026-09-08 19:57 snapshot. The Match clauses together reach 272 of the 438 files. Lexical clauses ran as text and parser matches; the two shape clauses (`box_edge`/`crop` restated, a parameter read as margins) ran with the parser over rule structure. Numbers below are files unless marked.

## 1. Callers

**`crop`, the inner view (a covered cell in the box's own frame)**

- `BoxFrame`: 134 files, 172 inits, 273 `inner` reads. 60 inits feed `grid` (a crop); 112 feed `cell` only, where the box is the set's own hull. Reads by shape: 196 full views `inner(K, P, P_in)`; 71 inner-set-only `inner(K, _, P_in)` (e.g. `142ca369` `marker_glyph`, `409aa875` and `6165ea8f` D4Map `src`/`dst`, `18447a8d` `margin_cand`); 2 membership-only; 2 negated (`414297c0` `outside`, `846bdb03` `out`). Representatives: `2c181942` `side_cell` (a box edge cell in the piece's frame), `1990f7a8` `paint` (a shape cell reseated by its quadrant), `18419cfa` `Parse.box` (closed interiors viewed from their box, read from `parse.box.inner`).
- `MarginFrame`: 4. `4e45f183` `border`, `4e7e0eb9` `border`, `ed74f2f2` `frame` feed one scalar to every edge (`uniform_delta` plus `crop`); `5daaa586` `crop` feeds `width` from `bound.low(D, K)`, one row per edge, and keeps `DirPack`.
- `Reframe` with a box outer: 5. `1990f7a8` `rel` (each box's margins inside the four boxes' joint span: box in a box's frame), `3345333e` `views` (grid cells in a candidate mirror frame, read both ways), `3befdf3e` `fig_rf` (figure cells relative to `params.fig_core_box`), `48d8fb45` `win` (`view` plus `window(B), geq(P, B)`: `crop` written by hand), `58f5dbd5` `crop` (`geq` inside `cell`: `crop` written by hand).

**`relative` / `compose`, the seat against a box with no covering test**

- `displacement` with a box operand: `2bcee788` `mirror` (a shape cell relative to a wall's box), `4938f0c2` `img` ×2 (ink relative to the block), `4c5c2cf0` `copy`/`orbit` (`P_rel` from the pivot's box, then `compose` back), `6cbe9eb8` `obox` (the box that seats an inner corner cell on an anchor: B = Q − Q_in), `7d18a6fb` `ink` (an intile cell to a canvas cell, giving a box), `045e512c` `fits`, `652646ff` `drawn`, `3ed85e70` `place` (an Occurrences placement minus `ORIGIN`). `4c177718` `placement` and `57aa92db` `seat` displace a cell of one frame to a cell of another; each column is typed `Inset` and holds the seated box.
- `compose` seating a relative cell in a box: `11dc524f` `home`, `3befdf3e` `paint`, `5b526a93` `covered` ×2 (a stored footprint and a square's inner cells seated in a crossing box), `409aa875` `placed`/`arrow_cell`, `626c0bcc` `covers`, `6c434453` `stamped`, `652646ff` `drawn`, `b1fc8b8e` `Parse.covers`, `2c0b0aff` `cross`, `412b6263` `copy_cell` (an inner cell through the stored `ring` inset).
- A box moved or grown by `compose`: `20981f0e` `landing` (box + offset), `28e73c20` `walk` (box + stored `inset`), `5c2c9af4` `outline` (box + `spread`, recursive: each outline is the inner one let out).
- Box let out by a uniform inset through `displacement(W, M, B)`: `3a301edc` `ring_box`, `52fd389e` `ring_box`, `543a7ed5` `ring_box`, `58f5dbd5` `crop_box`.

**`inside` / `interior` on a box**

- `Bbox.inside` reads: 65 files, 95 sites, all a domain cell covered by the box; 17 negated (listed under Spec). Domains other than the input grid: `40f6cd08` `covers` (inner positions), `4c7dc4dd` `repeat` (intile), `37d3e8b2`, `3dc255db`, `44d8ac46`.
- Direct `geq`/`gt` with a box: 15 + 10 files. Cell in box: `3a301edc`, `42f83767`, `446ef5d2` `span_cell`, `447fd412` `stamped`, `4c3d4a41` `inside` (stored `params.box`), `52fd389e`, `543a7ed5`, `5751f35e` `covered`, `7d1f7ee8` `enclosed`, `7ee1c6ea` `inside` (`gt`). Box nesting: `7d1f7ee8` `nested_rect` `geq(B, B_outer)`, `40f6cd08` `nested`, `63613498` `key` (against stored `params.panel`), `3eda0437` `Parse.seat.item` (a square inside a hole box), `5751f35e` `shadowed` `gt(B2, B)` strict. `geq(M, ORIGIN)` at `20981f0e` `landing`. `gt(P, ORIGIN)` off-border: `25e02866`, `3f23242b`, `5034a0b5`, `5b37cb25`, `689c358e`, `6a980be1`, `6cdd2623`, `846bdb03`.

**`box_edge` / `box_corner`**

- `BoxCells`: 20 files, 21 instances; `on_edge` read in 15 files (24 sites), `hole` in 13 (20 sites, one negated at `776ffc46`). Boxes fed from `Bbox.margin` (12), `DrawnRect.rect` (5), a local box relation (`446ef5d2` `rect`, `5b526a93` `site`, `5c2c9af4` `outline`, `6cbe9eb8` `obox`). Domains other than `in`: `3dc255db` `cavity.reach`, `444801d8` `box.grid`, `446ef5d2` `rect_cell`, `6b9890af` `frame_box.viewed`, `6cbe9eb8` `frame.cell`. `5c2c9af4` reads `on_edge(B, _, _)` as existence: the outline still draws on the grid.
- Hand-written through `inner` and `dist(_, D, 0)`: `212895b5` `Parse.seed`, `4290ef0e` `paint`, `42918530` `outline`, `4e469f39` `gap` ×2, `78332cb0` `port`.
- Corner through `inner` and `corner_anchor(_, P_in, ORIGIN)` or `corner_dist(P_in, Diag, 0)`: `4c177718` `placement`, `6cbe9eb8` `obox`.
- `Bbox.edge_cell` reads: 20 files, 24 sites, the set's cell on the box's side, feeding a cast or a tally (e.g. `7c66cb00` `fall`, `34cfa167` `cast.mark`); two negated. `Bbox.corner` reads: 11 files, 18 sites; three negated (`1e5d6875` ×2, `604001fa`).

**`Outlines` (`DrawnRect`)**: 7. `1a6449f1`, `1c786137`, `4c7dc4dd`, `776ffc46`, `810b9b61` feed `rect` into a `BoxCells` box; `6b9890af` reads `rect` for existence; `7d1f7ee8` nests rects with `geq`.

**The other Bbox readouts**: `margin` 53 files, 89 sites; `edge_min` 15 files, 19 sites, each `dist` on the box (e.g. `6ca952ad` `flush`, `19bb5feb` `rank.idx_set`); `extent` 30 files, 38 sites; `extents` 26 files, 33 sites.

**The readings**: `Shift` columns in 44 files (94 columns), every one a translation except `47996f11` `params.center([1, -1, 1, -1])`, a base. `Inset` columns in 8 files (15): `0934a4d8` `mosaic_margin` and the Determine chain, `28e73c20` `inset`/`walk`, `412b6263` `ring`, `48d8fb45` `win_delta`, `2697da3f` `arm_margin` hold a box or a per-edge frame change; `4c177718` `placement`, `57aa92db` `seat`, `5c2c9af4` `spread` are cell-to-box differences. Stored boxes typed `Position`: `3befdf3e` `fig_core_box`, `4c3d4a41` `box`, `63613498` `panel`, `995c5fa3` `box_color` (a table keyed by a box). `ORIGIN`: 35 files, 53 sites, read as the zero offset (Slide nodes, `displacement(_, ORIGIN, _)`), the whole frame (`6cbe9eb8` `obox`, `5587a8d0` `covers`, `20fb2937` `frame.grid`), the one cell of a 1×1 output (8 `out` heads), off-border `gt`, and the frame corner in `corner_anchor` (5 sites). `ShiftInvariance`: 7 files, every `delta` a translation. `jump_delta` 11 files, `step_delta` 8, every output a translation. `uniform_delta` outputs read as a box: `28e73c20`, `412b6263`, `5587a8d0` `center`, `5751f35e` `layer`; `edge_delta` outputs read as a box or a one-sided frame extension: `0934a4d8`, `2697da3f`, `45a5af55` `side`, `48634b99` `target`, `6165ea8f` `slot`. Box operations beyond the entry's list: `5b526a93` `site` splits two boxes into bands and composes the bands into a box; `3e6067c3` `corridor` reads `nearer(D, P, M)` against a box; `3d588dc9`, `689c358e`, `f25ffba3` read `dist`/`dist_pair` on a box; `2ba387bc`, `5dbc8537` feed boxes to `LexOrder.cell`; `1990f7a8` feeds boxes to `DiagPlacement.cell`.

## 2. Near-misses

- `2bcee788` `wall.cell` and `shape_box` at line 94: `same_dist` against a box, wanting the whole line across the grid; `box_edge`'s covering test cuts it to the edge segment.
- `Reframe` with an anchor-cell outer: `212895b5` `frame` (seed cell), `247ef758` `off` (a centered cell), `47996f11` `view` (stored center). The third column is consumed as an offset: `displacement`.
- Box-to-box `displacement` at `321b1fc6` `shift`, `34cfa167` `shift`, `3ed85e70` `place`: an offset between two boxes of one frame, no covering test.
- `axis_delta` at `4be741c5` `out`, `652646ff` `tile`, `78332cb0` `seat`: builds a cell from two counts (a frame of extent R+R2+1); the output is a Position, not an inset.
- `dist(P, D, 0)` as the frame border (`17829a00` `border_cell` and others): `box_edge(P, ZERO, D)` would be an indirection past a one-atom form.
- `1478ab18` `box_corner`: a different operation (the cell at one aligned cell's along-band and the other's across-band); it shares only the name.
- `b1fc8b8e` `params.canvas`: a cell set from `frame_pos`, matched by the parameter clause through `corner_anchor` and not a box.
- Instances named `box`: 137 in 132 files (53 `Bbox`, 81 `BoxFrame`, 2 `Frame2D`, 1 `BoxCells`); all rename under "every box readout is `box`".

## 3. Spec

- **`extent`/`extents` retirement.** 46 files, 71 sites read them, and many rules bind no frame cell (`6165ea8f` `Determine.block(N) :- blk.extent(_, _, N)`, `25094a63` `smallest.cand`, `5833af48` `tiles.dim`, `4e7e0eb9` `section`). `box_extent(b, p, a, n)` makes each add a cell atom only to name the frame. `Bbox` holds the set, so the extent is derivable inside the aggregate at no cost: the callers argue for keeping `extent` and `extents` as `Bbox` readouts.
- **Inner-set reads.** 71 `inner(K, _, P_in)` sites read the box's own frame as a position set with no grid cell named. `crop` needs its cell grounded, so each site adds a domain atom. A realized inner frame (the `Frame2D` of the box's extents) is what they read; the entry's matrix has no row for it.
- **Outset.** Four sites let a box out by a uniform inset through `displacement(W, M, B)`, and `5c2c9af4` grows a box by a cell-to-box difference. In the entry's names that is `relative(W, M, B)`, whose gloss ("M in W's frame") is not what the site means. The inset constructors take k ≥ 0, so the outset has no constructor; either the constructors admit the outset reading or `relative` documents it.
- **Bbox over offsets.** `20fb2937`, `3f23242b` (and `642d658d`, out of scope) feed `Shift` values to `BoxFrame.cell` and `ORIGIN` to `grid`, and read the seat as `inner($U(), ORIGIN, P)`. The typing rule keeps comp cell inputs `Position`; these sites feed `Offset`. The pointwise minimum is defined either way, so the rule's reason (reading the frame's extent) is what to state, not the type.
- **Negated readouts.** 25 negated reads in 22 files need a local wrapper after retirement: `inside` at `137f0df0`, `21f83797`, `256b0a75`, `3a301edc` ×3, `3ed85e70`, `4a1cacc2`, `52fd389e`, `543a7ed5`, `56ff96f3`, `58490d8a`, `58743b76`, `6ffbe589`, `7d18a6fb`, `7d7772cc`, `845d6e51`, `846bdb03`; `corner` at `1e5d6875` ×2, `604001fa`; `edge_cell` at `4c3d4a41`, `6cbe9eb8`; `hole` at `776ffc46`; `inner` at `414297c0`, `846bdb03`; `margin` at `447fd412`.
- **Name clashes.** Local relations `inside` (`4c3d4a41`, `5587a8d0`, `7e0986d6`, `7ee1c6ea`), `interior` (`17829a00`, `5034a0b5`, `694f12f3`), `crop` (`291dc1e1`, `6ffbe589`, `72ca375d`, `846bdb03`), `box_corner` (`1478ab18`); instances `crop` (10 files), `interior` (`7c66cb00`, `846bdb03`), `box` (137).
- **Stored boxes.** Eight parameters hold a box (four typed `Position`, four `Inset`); `995c5fa3` keys a table by one. Witness for `Box` as a Params type.
- **`DirPack` stays.** `5daaa586` feeds per-edge rows from an `Extremes` readout, as `4522001f` does.
- The prior survey's caller-only readings are all re-witnessed in scope: `geq(Box, ORIGIN)` (`20981f0e`), nesting (`7d1f7ee8`, `40f6cd08`, `63613498`, `5751f35e`), a box let out (`52fd389e`, `543a7ed5`, `3a301edc`, `58f5dbd5`), bands of boxes (`5b526a93`).

## 4. Reimplementations

Reimplementations:
- `/Users/davidlu/code/arc-workspace/programs/solvers/212895b5.dl` lines 44–46 (`Parse.seed`): `box.inner` plus `dist(P_intile, D, 0)` — `BoxCells.on_edge`.
- `/Users/davidlu/code/arc-workspace/programs/solvers/4290ef0e.dl` lines 127–129 (`paint`): `nest.inner` plus `dist(Q, D, 0)` — `BoxCells.on_edge`.
- `/Users/davidlu/code/arc-workspace/programs/solvers/42918530.dl` line 50 (`outline`): `box.inner` plus `dist(P_intile, D, 0)` — `BoxCells.on_edge`.
- `/Users/davidlu/code/arc-workspace/programs/solvers/4e469f39.dl` lines 43–46 and 49–52 (`gap`): `box.inner` plus `dist(P_inner, D, 0)` — `BoxCells.on_edge`.
- `/Users/davidlu/code/arc-workspace/programs/solvers/78332cb0.dl` lines 40–42 (`port`): `tile.inner` plus `dist(P_intile, D, 0)` — `BoxCells.on_edge`.
- `/Users/davidlu/code/arc-workspace/programs/solvers/4c177718.dl` line 148 (`placement`): `pay_box.inner` plus `corner_anchor(Diag_pay, P_inner, ORIGIN)` — `Bbox.corner` (the closed `Bbox-corner_cell.md` rests on this idiom; the entry's Spec already routes it to `box_corner`).
- `/Users/davidlu/code/arc-workspace/programs/solvers/6cbe9eb8.dl` line 64 (`obox`): `box.inner` plus `corner_dist(Q_in, Diag, 0)` — `Bbox.corner`, same note.
- `/Users/davidlu/code/arc-workspace/programs/solvers/3eda0437.dl` lines 47 and 54 (`Parse.box_ink`, `Parse.hole_cell`): `geq(P, B)` over the domain against `span.margin` — `Bbox.inside` with `grid` fed, keyed by the collapsed box instead of the span key.
