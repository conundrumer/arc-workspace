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
- A line that merely holds a member: 20981f0e `lattice.divider`, a dot marking its line on each axis; 8731374e `flaw_line`, the crop cells sharing a line with a flaw, negated for the other cells; 8ba14f53 `block_line`, the lines a block spans, counted into `offset`.
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
