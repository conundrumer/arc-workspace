# `LineCover<Key>` — the lines a cell set covers whole

The lines of a frame that a keyed cell set covers with no cell left over, per key: every cell of the line is a member, so the line is a full row or column of the set. It is how a solver finds a divider, a blank line, or a line drawn all the way across, when what marks the line is membership in a class and not agreement on one value. `LineColor` states the agreement reading, which pairs a line with the one color it holds; a set covering a line of several colors passes here and fails there.

```
.comp LineCover<Key> {
    // The frame's cells, per key.
    .decl cell(key: Key, p: Position)  // input

    // The axes whose lines are read, per key.
    .decl axis(key: Key, a: Axis)  // input

    // The covering set, per key.
    .decl member(key: Key, p: Position)  // input

    // A cell of the line that the set leaves out.
    .decl gap(key: Key, a: Axis, l: Position)
    gap(K, A, L) :- cell(K, P), !member(K, P), axis(K, A), split(P, A, L, _).

    // The set covers every cell of the line at l. l is the along component
    // `split` gives, so the line runs perpendicular to a — the convention
    // `DividerFrame.divider` takes.
    .decl line(key: Key, a: Axis, l: Position)
    line(K, A, L) :- cell(K, P), axis(K, A), split(P, A, L, _), !gap(K, A, L).
}
```

Not: the one color a whole line holds (`LineColor`); a line that merely holds a member somewhere; a maximal contiguous run of members inside a line (`Runs`); `DividerFrame`, which takes the cutting lines as its input; a covered region that is not a full line; a per-line count or extremum.

Match: a defect relation whose body tests one cell against a class, negated in a second rule over the same line. The line is keyed two ways. It is a line position that `split` produces, under either convention, along or across; or it is a cell of the line, joined through `same_line`, with no line position anywhere. Grep signature: `grep -ln 'split(P, A\|same_line(' programs/solvers/*.dl`, then read for a per-line relation that a later rule negates. The hand-written shape is matched with the parser.

Survey: 2026-09-09 02:55
Survey: 2026-09-09 03:20 — the solvers at or after the first survey's time.
Survey: 2026-09-09 06:08 — the solvers at or after the second survey's time.

The third survey read the twenty-one solvers whose file time is at or after 03:20. Beyond `6350f1f4` it found no caller, and no hand-written lib primitive. It reached the shape through a parser pass that lists every negated relation beside the body atoms of the rules defining it, so a per-line defect keyed some other way than by a line position would still show; of the forty-four negated relations in the scope, the three per-line defects over a cell class are the ones this entry already holds.

Survey: 2026-09-10 02:12 — the solvers at or after the third survey's time, 332 of them, `6e4f6532` excluded.

The fourth survey read every negated relation whose defining rule binds a line, the per-line `Unanimous`/`Tally`/`Mode` instances, and covers written as a count or a walk. Two new callers: `67a423a3` and `465b7d93`, listed below. No reimplementation: the sites read call the lib primitives they need. Near-misses of the recorded kinds: a line that merely holds a member (`21f83797` `on_line`, `412b6263` `copy_line`, `45bbe264` `cross`, `6a980be1` `line_cell` and `on_pattern_line`, `1bfc4729` `ink` under `$MarkLine`); co-occurrence with no cover (`5ad8a7c0` `crossed`, `195c6913` `on_strip`); the converse containment against an edge line (`6ad5bdfd` `off_wall_edge`); an edge line with no class tested (`291dc1e1` `Parse.border`); an edge line that merely holds a member (`195c6913` `field`, `4be741c5` `touch`); a box outline drawn whole, not a line (`1c786137` `misdrawn`); and the `LineColor` `Unanimous` callers, all listed in `LineColor.md`.

Spec, from the new sites:

- `67a423a3` reads the cover per cell on both axes and tags its line by the axis it runs along, so it is a third site for the `covered(key, a, p)` readout and a fifth for the across convention: `crossing` would read `covered(K, A, P), perp(A, A2), covered(K, A2, P)`.
- `465b7d93` covers a box's edge line, not the grid's, so the recorded edge-line migration (a full-grid instance selected with `dist(L, D, 0)`) does not reach it; the select goes through the box margin or through `BoxFrame.inner`, four rules for one. Caller-only evidence that the edge-line class stays cheaper hand-written.
- The single-color boundary stands: three `LineColor` sites (`272f95fa`, `4c177718`, `54d9e175`) test the agreed color against a named parameter, which `member` states directly; five (`20fb2937`, `247ef758`, `2546ccf6`, `39e1d7f9`, `4e7e0eb9`) read `!params.bg(Col)` on it and belong to `LineColor` as written.

## Callers

Twenty-one solvers, none of them family siblings. Each derives a per-line defect over a cell class and negates it. Six cover with a class of several colors, so only this operation states them; fifteen hold to a single color, so `LineColor` states them too.

Multi-color class:

- `5daaa586` — `gapped`: a row or column with no background cell is a divider, and the four dividers bound the crop. The line position is consumed as a Position by `dist`.
- `469497ad` — `broken`: a line with no bg cell is the legend, which the block excludes.
- `178fcbfb` — `Determine.bare`: a dot's line in the output holds no bg cell, covered by the dot's own color or by an overriding one, so the dot paints that family.
- `6350f1f4` — `content_line` negated: a line covered by the separator color and the noise color is a separator, and its position feeds `DividerFrame.divider` under the axis it was split on.
- `67a423a3` — `gapped` under `$Span`: a row or column with no bg cell is a line, and the crossing is where a line of each axis meets; the two lines hold different colors. Written on the across convention, consumed per cell through `split` on both axes.
- `6e4f6532` — `line_bg` negated in `wall`: a line with no bg cell is a wall, whose cells are read per cell through `split` on the line position; bg comes from `Mode`.

Blank line, the member set being the bg cells: `0b148d64` `ink_slice`, `137f0df0` `block_line`, `18447a8d` `line_ink`, `1be83260` `inked_line` over a cropped region, `1c0d0a4b` `ink_line`, `42918530` `inked_line`, `4f537728` `inked_line`, `c1d99e64` `has_ink`, `5dbc8537` `inked_line`, whose bg comes from `Mode` rather than from a parameter, and whose uncut lines split the grid into a template panel and a piece panel.

`137f0df0` keys the cover by a cell of the line rather than by a line position: `block_line(A, P) :- in(P, _), axis_elem(A), block(Q), same_line(A, P, Q).` The negation still says the bg set covers P's line, and the axis tag is in the `same_line` sense.

Named color: `18286ef8` `line_broken` over `params.divider`; `2e65ae53` `broken` over the modal ink, keyed by `Ident` across one component's box interior; `77fdfe62` `off_line` over `params.line`, written twice, in the program and in `Determine`.

Edge line, keyed by `Dir`: `13713586` `wall_defect`, the one edge whose whole border line is wall-colored, and `508bd3b6` `open_edge`, the wall covering a whole side. `465b7d93` `edge_hole` under `$Stretch` is the same shape over the shape's own box edge (`BoxCells.on_edge`), the covering set being the one derived mark color. The two write one rule byte for byte: `dir_elem(D), in(P, Col), dist(P, D, 0), !params.wall(Col)`. The operation serves them at the cost of three input rules in place of that one, or of a full-grid instance whose result they select with `dist(L, D, 0)`.

Eight callers — `18447a8d`, `1be83260`, `42918530`, `4f537728`, `18286ef8`, `2e65ae53`, `77fdfe62`, `5dbc8537` — write `DividerFrame.divider` as the code form's `line` rule verbatim, so their migration is `frame.divider(K, A, L) :- cover.line(K, A, L)`.

## Near-misses

- A line that merely holds a member: `ca8f78db` `pattern_row`, in its positive reading; `4290ef0e` `line_cell`, the line's cells of one ring color, with no cover test; `bdad9b1f` `line`, drawn from one or two ink cells on it; `5e6bbc0b` `line`, plain membership with no defect.
- Part of a line: `22eb0ac0` `edge_match`, which compares the line's two end cells; `5e6bbc0b` `packed`, the cells of the line nearest the fall edge, counted off a `Tally`.
- The converse containment, a set lying inside one line rather than a line inside a set: `12997ef3` `off_axis`; `22425bda` `off_family` over `collinear`; and against an edge line, `3bd67248` `off_edge`, `3ac3eb23` `Determine.off_edge`, `2601afb7` `Determine.anchor_bad`.
- A universal that is not over a line's cells: `4be741c5` `gapped`, over the colors of an axis, a name collision only; `4ff4c9da` `covered`, over one color's cells; `60a26a3e` `ring_gap`, over a cell's four cardinal neighbors.
- A covered region that is not a full line: `1fad071e` `Determine.mismatch_edge`, the N cells nearest an edge; `af902bf9` `open_pair` and `604001fa` `Parse.missing_corner`, each over a box's four corners.
- Agreement between two grids rather than membership in a class: `3618c87e` `Determine.replaced` over `out_slice`.
- Co-occurrence on a line, with no cover: `50aad11f` `shared_line`, `3345333e` `damaged`, `140c817e` `crossed`, `38007db0` `band_peer`, `4ff4c9da` `aligned` over box margins.
- An edge line with no class tested: `17829a00` `border_cell`, negated into the interior, which takes both edge lines of `params.axis` unconditionally. The recorded `13713586` and `508bd3b6` edge-line callers do test their border line against a color class.
- A fold keyed by something other than a line: `516b51b7` `Determine.phase_color` and `97999447` `Determine.slot_color`, each a `Unanimous` over a period phase.
- The `LineColor` `Unanimous` callers as a class, which read a color that no member set yields.

## Spec

The code form above already carries these answers.

- **`gap` is comp-internal.** All sixteen callers consume the defect only under negation. The one site that reads a per-line defect positively, `ca8f78db` `pattern_row`, is a near-miss. Admitting it later needs both readouts, and it diverges from the code form on a row holding no clean cell, where `line` is silent and `!pattern_row` holds.
- **`member` takes the set the callers do not name.** Every caller derives the breaking class — ink, block, non-wall, non-separator-colored — and negates it per line. Feeding `member` costs one rule at each site, and the covering set is the operation's own vocabulary.
- **The per-key `axis` and `cell` inputs stand.** Most callers feed `axis_elem`, but `18447a8d` restricts to its band axis and `13713586` and `508bd3b6` want one axis per `Dir` key. `1be83260` feeds a cropped region, `2e65ae53` keys by `Ident` over per-component box interiors, and `77fdfe62` and `178fcbfb` key by `Example` to share the derivation with `Determine`.
- **Two sites read the cover per cell.** `137f0df0` consumes it as `!block_line(A, P)` and never as a line position, and `178fcbfb` identifies its line by a cell through `same_line`. Under the code form each migrates to `perp(A, A2), cover.line(K, A2, L), split(P, A2, L, _)` — three atoms where the site writes one negation. A `covered(key, a, p)` readout — p lies on a line of family a that the set covers — would serve both, with the axis in the `same_line` sense that both want.
- **The `a` column names the along convention.** Eleven callers split on along, and the seven `DividerFrame` callers feed `l` straight through. Four read across — `137f0df0`, `1c0d0a4b`, `c1d99e64`, `469497ad` — and get the transposed tag; `178fcbfb` identifies the line by a cell through `same_line` and needs a `perp` as well. This is the friction `LineColor` records.

## The boundary with `LineColor`

Neither operation subsumes the other. `LineColor` cannot state `5daaa586`, `469497ad`, or `178fcbfb`, whose covering sets hold several colors. `LineCover` cannot yield the color column that most `LineColor` callers read. Formally `LineCover` generalizes `LineColor` — key by (key, color) with `member` the cells of that color, and `line([k, col], a, l)` is `LineColor.line(k, a, l, col)` — but that instantiation costs a cross product over colors and loses `mixed`, which `746b3537` and `25d8a9c8` read and never the color.

Three sites in the third survey's scope sharpen the boundary. `60d73be6` `line_color` is the `LineColor` code form over both axes of the grid, and it discards the color (`line_color.value([A, L], _)`) — so a caller can want the agreement and no color at all, and still have no class to feed `member`. `5daaa586` calls both operations: `gapped` finds its dividers by membership in a multi-color class, and `side` reads a color off the crop box's four edge lines, which no member set yields. `5ecac7f7` `Parse.line_color` bears on the single-color question below: it is written as agreement, and it reads the color for nothing but a test against `params.sep`, which `member` states directly.

`LineColor`'s hand-written blank-line class and its `469497ad` near-miss are all this operation's code form. `469497ad` belongs here alone: its class is multi-colored, so a legend line of two non-bg colors passes here and fails there. The fourteen single-color sites hold to one color per input — a one-fact parameter, or `5dbc8537`'s derived modal bg — so the cover and the agreement coincide on every input and either operation states them exactly. Which one takes them is a promotion-time choice.

Survey: 2026-09-11 04:13 — the solvers since 2026-09-10 02:12.

Callers:

8a371977 off_line — negated in `cut.divider`: a line across either axis with no ink cell (the member set being the bg cells) is a divider, and the position feeds `DividerFrame.divider` on the along convention; the migration is `cut.divider(K, A, L) :- cover.line(K, A, L)`.

Both recorded callers in the scope still write the operation: 137f0df0 `block_line`, keyed by a cell of the line through `same_line`, and 5dbc8537 `inked_line`, the bg-covered lines feeding `panels.divider`. No other caller: across the 82 solvers, the parser pass listed 298 negated relations with the bodies of their defining rules; 30 of those bodies bind a line or an edge, and beyond the three above, each is a near-miss below.

Near-misses:

- A per-line defect read positively, never negated: 85b81ff1 `line_hole`, a line holding a bg cell, conjoined with `line_ink` into `sortable`; the rule that keeps the other lines negates `sortable`, so `!sortable(L)` is the union of two covers, by bg and by ink, and the site reads the defect and not the cover.
- A line that merely holds a member: 20981f0e's tiling `divider`, a dot marking its line on each axis; 8731374e `flaw_line`, the crop cells sharing a line with a flaw, negated for the other cells; 8ba14f53 `block_line`, the lines a block spans, counted into `offset`.
- The converse containment, a set lying inside one line or one outline: 538b439f `reach` with `thin`, a component that reaches one line on some axis; 890034e9 `stray`, a cell of the outline's color off the outline, negated into `frame`.
- A universal not over a line's cells: 8f215267 `in_hole`, an object with a cell in a rectangle's hole, negated into `frame`.
- An edge line that merely holds a member: 846bdb03 `bar`, a non-bg non-corner color on a border line, and `touches`, a placed cell of that color on that edge; 8abad3cf `Determine.reaches`, a color at edge d, negated into `short_of`; 22eb0ac0 `edge_match`, which compares the line's two end cells.
- An outline or edge line with no class tested: 291dc1e1 `Parse.border`; 8cb8642d `frame_color`, the colors on a box outline, negated to find the marker.
- A line drawn from a member on it: 412b6263 `copy_line`; bdad9b1f `on_line`.
- The `LineColor` `Unanimous` class, which reads a color that no member set yields: 538b439f `line_color`; 855e0971 `line_color`, reading `mixed` and the value; 8e1813be `stripe`, reading `clash` and the value; 88a62173 `line_color`, discarding the color and testing no class; 8d510a79 `Parse.line_color`, testing `!params.bg(Col)` on the value; 7c66cb00 `ends` and `interior`, agreement over the two parts of a line; 8886d717 `edge_color`, agreement over each edge line; 84ba50d3 `line_color`, testing the value against `params.divider`.

Spec:

- The operation's interface stands. 8a371977 is the blank-line class on the along convention feeding `DividerFrame`, the migration the entry already records for eight callers.
- 85b81ff1 is a second site, beside `ca8f78db` `pattern_row`, that reads the per-line defect positively. Its `sortable` is `line_ink ∧ line_hole`, and the code form's `gap` is comp-internal, so the site cannot state `sortable` through `line` without a double negation over two instances. Caller-only evidence for exposing `gap`; the entry's judgment that `gap` stays internal is not changed by one site.
- 84ba50d3 `line_color` is a fourth `LineColor` site that tests the agreed color against a named parameter, which `member` states directly, so either operation states it exactly; the single-color boundary the entry records is unchanged.
- 8d510a79 tests `!params.bg(Col)` on the value and belongs to `LineColor` as written, as the five recorded sites of that kind do.

Reimplementations: none.

The parser pass listed, per solver in the scope, every negated relation with the body atoms of its defining rules, flagging the bodies that bind a line or an edge (`split`, `same_line`, `dist` and its kin, `on_edge`, `edge_cell`), every `Unanimous`, `Tally`, `Mode`, `Between`, `Ray`, `Slide`, `DividerFrame`, `BoxCells`, and `Bbox` instance with its input rules, and every source line matching the grep signature: 298 negated relations, 30 with a line-binding body, 207 instance input rules, and 23 solvers hit by `split(P, A` or `same_line(`. The `Tally` and `Ray` instances were read for a cover written as a count or a walk; none is one.

Survey: 2026-09-14 02:35 — the solvers since 2026-09-11 04:13.

Callers:

7837ac64 `gapped_line` — a row or column holding a bg cell is the defect; its negation gives `on_line(P, A)`, the cover read per cell on both axes, and `node` crosses the two axes with `perp` to find the tiling crossings.
7c8af763 `bg_line` — a line with no bg cell is a full line of the tiling, and the negation feeds `tiles.divider` on the along convention.
7e576d6e `broken` — a line with no bg cell is a divider, bg coming from a `Mode` rather than from a parameter, and the negation feeds `cut.divider`.
941d9a10 `Parse.off_line` — a line whose every cell carries the separator color cuts the blocks; written inside a keyed `Parse` comp, the negation feeding `cut.divider`.

Seventeen recorded callers sit in the scope and each still writes the operation: 0b148d64 `ink_slice`, 137f0df0 `block_line`, 13713586 `wall_defect`, 18286ef8 `line_broken`, 18447a8d `line_ink`, 1be83260 `inked_line`, 2e65ae53 `broken`, 42918530 `inked_line`, 465b7d93 `edge_hole`, 469497ad `broken`, 4f537728 `inked_line`, 5daaa586 `gapped`, 5dbc8537 `inked_line`, 6350f1f4 `content_line`, 6e4f6532 `line_bg`, 77fdfe62 `off_line`, 8a371977 `off_line`. Three of the four new callers write the code form's `line` rule verbatim, so their migration is one rule: `<inst>.divider(K, A, L) :- cover.line(K, A, L)`.

No further caller: across the 483 solvers the parser pass listed 1666 negated relations, 155 of them with a defining rule that binds a line or an edge, and each of those beyond the twenty-one above is a near-miss below. The pass over per-line relations that no rule negates found three sites reading a per-line defect positively, all near-misses.

Near-misses:

- A per-line defect read positively and never as the cover: 234bbc79 `inked_line`, the lines holding ink, which packs them through `OrderFrame` so the blank lines close up; 85b81ff1 `line_ink` with `line_hole`, conjoined into `sortable`; ca8f78db `pattern_row`.
- A line that merely holds a member: 20981f0e's tiling `divider`, a dot marking its line on each axis; 363442ee `panels.divider`, 8597cfd7 `panels.divider`, 9356391f `panel.divider`, and 6e453dd6 `cut.divider`, each a line carrying one cell of a named color; 65b59efc's tiling `divider`, two adjacent separator cells marking the line they run along; 247ef758 `header`, a mark on a border cell naming its line; 9344f635 `Parse.line_col`, a line holding a segment; 21f83797 `on_line`; 412b6263 `copy_line`; 4290ef0e `line_cell`; 8731374e `flaw_line`; 8ba14f53 `block_line`; 6a980be1 `line_cell` and `on_pattern_line`.
- A line drawn from a member on it: 689c358e `mark`; 54d82841 `mark_cell`; 917bccba `Parse.crossing`; c1990cce `arm`, a diagonal line from the seed; 2281f1f4 `marked` and `selected`; 8403a5d5 `dotted`; 56dc2b01 `back_line`, the grid line one step behind a resting mover's face.
- Co-occurrence on a line, with no cover: 1efba499 `crossing`; 16b78196 `catch`; 8a371977 `screened`; 84ba50d3 `pierced`; 50aad11f `shared_line`; 3345333e `damaged`; 38007db0 `band_peer`.
- The converse containment, a set lying inside one line rather than a line inside a set: 12997ef3 `off_axis`; 88bcf3b4 `bent`, an object with cells on two lines, negated into `pole`; and against an edge line, 0a938d79 `on_axis_edge` with `off_axis_edge`, 3979b1a8 `Determine.growth_mismatch`, 3ac3eb23 `Determine.off_edge`, 3bd67248 `off_edge`, 6ad5bdfd `off_wall_edge`, f45f5ca7 `Parse.off_edge`.
- A box outline covered whole, not a line: 14b8e18c `border_gap`, a cell of the box's border the object does not hold; 810b9b61 `edge_gap`; 446ef5d2 `spills`, a placement showing on the rectangle's edge, negated into `fit`; 1c786137 `misdrawn`. Each binds the `box_edge` direction as a wildcard, so the covered thing is the four sides together. The recorded 465b7d93 `edge_hole` binds that direction and is one line per side.
- An outline or edge line with no class tested: 58c02a16 `sep_cell`; 5c2c9af4 `drawn`; 2d0172a1 `ink`; 928ad970 `drawn`; 6cbe9eb8 `on_edge`; 890034e9 `on_edge`; 291dc1e1 `Parse.border`; 17829a00 `border_cell`; 4c3d4a41 `Determine.comb_edge_cell`; 8cb8642d `frame_color`.
- An edge line that merely holds a member: 825aa9e9 `floor_color` and `standing`; 305b1341 `legend`; 5adee1b2 `legend_entry`; 271d71e2 `Determine.edge_color`; 4be741c5 `touch`; 846bdb03 `touches`; 3a301edc `rect_color`; 57edb29d `field`.
- A cell keyed by its line, with no universal over the line: 963c33f8 `piece`, a piece cell under its across position on the fall axis; 017c7c7b `cell_line`; 66ac4c3b `line_ink`; 90c28cc7 `line_cell`; 484b58aa `si_line.cell`; 673ef223 `line`; 2bee17df `line_of`; 95a58926 `cell_split`; 52364a65 `obj_line`; 67636eac `box_line`.
- A slab rather than a line: 42f83767 `legend_cell`, the ink inside the stencil strip's band of lines.
- The `LineColor` `Unanimous` class, which reads a color that no member set yields: the value discarded, 135a2760, 38007db0, 458e3a53, 5a719d11, 7491f3cf, 81c0276b, 88a62173 and 60d73be6, each `line_color`; the value tested `!params.bg`, 0bb8deee, 20fb2937, 2546ccf6, 39e1d7f9, 7c008303, 8d510a79, 92e50de0, each `line_color`, 4e7e0eb9 `line_col`, and 83302e8f `line_color` over a `Mode`; the value read for itself, 855e0971 `line_color` and 8e1813be `stripe`, both reading `clash` as well, 1a2e2828 `line_color`, 50a16a69 `line`, 7d7772cc `line_color`, 7ed72f31 `mirror_line`, 5b692c0f `line_pick`, and 66ac4c3b `line_color` over a line's ink alone.

Spec:

- The per-cell readout gains a site. 7837ac64 `on_line` derives the cover per cell on both axes and crosses the two with `perp`, the shape recorded for 67a423a3 `crossing`; with 137f0df0 and 178fcbfb that is four sites that consume the cover as a cell predicate and not as a line position. A `covered(key, a, p)` readout beside `line` would serve all four, and 7837ac64 wants the axis in the along sense the code form already gives.
- The interface stands for the other three new callers. 7c8af763, 7e576d6e and 941d9a10 are the blank-line and named-color classes on the along convention feeding `DividerTiles`, and 941d9a10 writes them inside a keyed `Parse` comp, which the `Key` type param already admits.
- Two sites write the blank-line cover through the agreement fold: 780d0b14 `line_color` and 7d419a02 `line_color` each test `params.bg(Col)` positively on the agreed color, so the member set is the bg cells and this operation states them exactly, with no color column spent. Three more test the value against a class the program already names — 78332cb0 against `params.sep`, and 538b439f and 5545f144 against a derived modal field color, as 5dbc8537's derived bg does — so the single-color boundary the entry records now covers nine sites in all.
- Three sites read the per-line defect positively. 234bbc79 `inked_line` joins ca8f78db `pattern_row` and 85b81ff1 `line_hole`. Each can still be stated from `line` alone, at the cost of a frame atom under a second negation, and 85b81ff1 needs two instances for its `sortable`. The entry's judgment that `gap` stays comp-internal now costs three sites rather than two.
- The `Not:` line's exclusion of a covered region that is not a full line is exercised: 14b8e18c `border_gap`, 810b9b61 `edge_gap`, 446ef5d2 `spills` and 1c786137 `misdrawn` all cover a box outline whole, keyed by the object or the placement. They are one shape among themselves and none of them wants a line, so they argue for a separate operation and not for widening this one.

Reimplementations: none.

The search ran three parser passes and one grep pass over the scope. The first listed every negated relation with the body atoms of the rules defining it, 1666 in all, and flagged the 155 whose definition binds a line or an edge through `split`, `same_line`, `box_edge`, `same_dist`, `divide_slab`, `crop`, or a `dist` against 0. The second listed the input rules of every `Unanimous`, `Tally`, `Mode`, `Between`, `Ray`, `Slide`, `DividerTiles`, `OrderFrame`, `Excess`, `Extremes`, `ArgExtremes` and `KeyedSetCompare` instance whose body binds a line, 101 rules, read for a cover written as a count or an agreement; none is one. The third listed every per-line relation that no rule negates and whose body tests a class, for a defect read positively. The grep signature hit 134 solvers, and the 36 of them that neither parser pass reached key cells by their line or pair cells on one line.

Survey: 2026-09-14 02:44 — the solvers since 2026-09-14 02:35.

Callers:

4e7e0eb9 `mid_bg` — the middle line of a section's field holds a bg cell; its negation gives `divider(P_sec, A, $Whole())`, so the member set is the non-bg cells and the divider is the line they cover whole. The line is named by the key (section, axis) and never by a line position.
95a58926 `gapped` — a grid line holding a bg cell; its negation gives `located(A, P_across, $Whole())`, the lines the non-bg cells cover. Written on the across convention, and consumed per cell through `on_mesh`, which `crossing` crosses on both axes with `perp`.

Two recorded callers sit in the scope and each still writes the operation: 6e4f6532 `line_bg`, negated in `wall`, and 941d9a10 `Parse.off_line`, negated into `cut.divider` on the along convention.

No other caller. Across the 23 solvers the parser pass listed 122 negated relations with the body atoms of the rules defining them; 17 of those bodies bind a line or an edge directly, and the rest were read one level up through the relations they bind, which is how both new callers surfaced. A second pass listed 32 per-line relations that no rule negates, for a defect read positively; beyond 85b81ff1 it found none.

Near-misses:

- A per-line defect read positively and never as the cover: 85b81ff1 `line_ink` with `line_hole`, conjoined into `sortable`, as recorded.
- A line that merely holds a member: 4e7e0eb9 `divider` under `$Any()`, an inked cell on the line away from the crossing; 963c33f8 `piece`, a piece cell keyed by its across position on the fall axis; 84ba50d3 `line_of`, a cell under its line with no class tested.
- Co-occurrence on a line, with no cover: 9473c6fb `tie`, two marks at one distance from edge d; 963f59bc `anchor`, a mark and a shape cell on one line of the mirrored axis; 84ba50d3 `through`, a shape cell past a divider line, and `pierced`, a divider cell a landed shape shares a line with.
- The converse containment, a set lying inside a region rather than a line inside a set: 93c31fbe `off_side`, the content wholly on one side of a box's midline, negated into `mirror_axis($Clear())`.
- A universal that is not over a line's cells: 93c31fbe `open_corner`, over a spanned box's four corners; 8a6d367c `pattern_cell`, negated into `contradicted`, over the blocks of a shape's tiling; 94414823 `inner`, an outline's interior; 95990924 `side`, over a cell's four cardinal neighbors.
- An edge line that merely holds a member: 8abad3cf `Determine.reaches`, a color at edge d, negated into `short_of`; 9473c6fb `spans`, a mark on edge d and a mark on the opposite edge; 95755ff2 `source`, a non-bg non-wall cell on the border it faces away from.
- An outline or edge line with no class tested: 4c3d4a41 `Determine.comb_edge_cell`, a comb cell on the comb box's d-side edge, negated into `refuted_dir`; 8a6d367c `wall_cell`, the drawn rectangle's outline.
- The `LineColor` `Unanimous` class, which reads a color that no member set yields: 7491f3cf `Parse.line_color`, the value discarded into `frame.divider`; 84ba50d3 `line_color`, the value tested against `params.divider`; 4e7e0eb9 `Determine.line_col`, the value tested `!params.bg`; 5545f144 `line_color`, the value tested against the derived modal field color. All four are recorded.

Spec:

- The line named by the key alone gains a site. 4e7e0eb9 feeds one line per (section, axis) key, so it reads no line position and its `divider` carries the axis as a column. It joins 13713586, 508bd3b6 and 465b7d93, whose lines are named by a `Dir` key. Under the code form it costs two input rules and a `line(K, A, _)` read in place of the one negation the site writes. This is the fourth site of the shape, and the first that keys a line by a region of the grid rather than by an edge direction, so the cost the entry records for the edge-line class is not confined to edges.
- The per-cell readout gains a site. 95a58926 `on_mesh` derives the cover per cell and `crossing` crosses the two axes with `perp`, the shape recorded for 67a423a3 and 7837ac64; with 137f0df0 and 178fcbfb that is five sites consuming the cover as a cell predicate. A `covered(key, a, p)` readout beside `line` would serve it, and 95a58926 reads across, so it takes the transposed tag the entry records as friction.
- The per-key inputs stand, and two sites sharpen why. 95a58926 holds the cover as `$Whole()` beside a `Mode` fold as `$Predominant()`, and 4e7e0eb9 holds the cover as `$Whole()` beside a merely-holds-a-member rule as `$Any()`. Each case writes into a shared `located` or `divider` relation, so the operation must instantiate for one case while a peer case feeds the same consumer. The `Key` type param and the per-key `cell` and `axis` inputs already admit that.
- The single-color boundary is unchanged. The four `LineColor` sites in the scope are all recorded, and none of them tests a class that `member` could state and that the entry does not already count.

Reimplementations: none.
