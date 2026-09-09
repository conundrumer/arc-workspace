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

- `BoxCells` sites: 14, with 10 `on_edge` and 8 `hole` reads. `on_edge` is `geq` plus `same_dist` verbatim, and `hole` is `gt`, so the retirement is exact. `14b8e18c`, `1c786137`, `21897d95`, `256b0a75`, `292dd178`, `2d0172a1`, `3de23699`, `3dc255db`, `4347f46a`, `444801d8`, `446ef5d2`, `465b7d93`, `50cb2852`, `bb43febb`.
- Hand-written through `inner` and `dist(_, D, 0)`: 5. `15660dd6` `ring_pos`, `212895b5` `Parse.seed`, `42918530` `outline`, `4290ef0e`, `4e469f39`. The closed entry `Bbox-corner_cell.md` named this operation as the edge form with the wider caller base.

`Outlines`: 3. `1a6449f1` `hole`, `1c786137` `bcells.box`, `4c7dc4dd` `box.cell`. All three read `rect` and then `gt`.

The readings:

- `Shift` or `Inset` in a type position: 63 files, 155 `Shift` columns and 19 `Inset` columns in 8 files.
- A stored Box typed `Position`, read by `geq` directly: `4c3d4a41` `params.box`. Solver-local Box relations typed `Position`: 15 files, among them `1a6449f1` `hole`, `2b9ef948` `box`, `3eda0437` `box_ink`, `40f6cd08` `nested`, `522fdd07` `shrunk`.
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
