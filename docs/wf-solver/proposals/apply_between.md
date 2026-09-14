# `apply_between` — a D4 transform read in one frame and seated in another

The image of a cell under a D4 element, read in the frame one Position places and seated at the frame another places: the cell is viewed from the source frame, transformed there, and composed onto the target frame. `apply_about` is this with one frame for both, and it cannot state the two-frame form: a reflection that exchanges two lines turns about their midline, which for an odd separation is no cell, and a copy that turns as it moves has a source and a landing with no shared origin. The two frames need no relation to the cell or to each other; each is any Position the flip or turn fixes as its origin.

```
.decl apply_between(d: D4, p_src: Position, p_dst: Position, p: Position, p_out: Position) inline
apply_between(D, F_src, F_dst, P, P_out) :-
    relative(F_src, P, V), apply(D, V, V2), compose(F_dst, V2, P_out).
```

Not: `apply_about` (one frame — a rule whose view and seat bind the same Position); `apply` (the grid's own frame); a seat with no transform (`relative` and `compose` around a stored or searched offset, as a stamp placement or a copy reads); a transform inside a decomposition's inner frame reseated by `concat` or a `crop` read backward, where no Position places the frames; a landing by an Offset searched over and keyed, which many origin pairs produce.

Match: a rule, or a chain of rules through a stored Offset, that binds two distinct Positions F_src and F_dst and holds all three of `relative(F_src, P, V)` — or a `crop(P, B, V)` whose box B is F_src — `apply(D, V, V2)`, and `compose(F_dst, V2, P_out)` — or a `crop` whose box is F_dst, read backward — in either compose argument order; and the same shape reached through two `apply_dir`-free steps, a grid-frame `apply` followed by a `jump` or a `compose` with the relative offset of the two frames. Grep signature: files holding both `relative` (or `crop(`) and `apply(` and `compose(`; `grep -n 'relative\|crop(\|apply(\|compose(' programs/solvers/*.dl` then read the rules that hold all three with two frame Positions.

Survey: 2026-09-09 22:10 — the whole corpus.

That pass read the whole corpus, 610 solvers, by the grep signature and by a parser pass over every rule holding a bare `apply` atom, tagged by whether the same rule holds a view (`displacement`, `.inner`), a seat (`compose`), or a `jump`. 158 rules in 105 files name a D4 element; 49 of them hold `apply` beside a view, a seat, or a jump. Nine callers, listed below. Its near-misses: the one-frame sites, which are `apply_about`'s callers; a landing by a Shift no origin produces, searched (`0e206a2e`, `412b6263`, `1acc24af`, `50f325b5`, `b7cb93ac`, `0dfd9992`, `08573cc6`, and the RIGID files `142ca369`, `150deff5`, `269e22fb`, `3aa6fb7a`, `3d588dc9`, `409aa875`, `4c177718`) or a grid-frame flip then a `jump` by a stored or scalar amount (`3631a71a` with its sibling `af22c60d`, `496994bd`); `1b60fb0c`, whose translation is the displacement of one ink cell's turned image from another, collected over every ink pair into a placement set — the Shift is the model's object, not one pair of frames; a decomposition frame no Position places (`833966f4`, `e3497940`, `47c1f68c`, `5a719d11`, `8e5a5113`, `eb281b96`, `e9afcf9a`, `4e7e0eb9`, `103eff5b`, and the tile-arrangement solvers); `apply` in the grid's own frame with nothing seated.

## Callers

- `66ac4c3b` — `painted`: every ink cell read from one marker line's frame, flipped across the marker axis, and seated at the other marker line: the reflection that exchanges the two lines. The frames are the lines' own axis-only Positions, and the rule states its own domain test.
- `4938f0c2` — `img`, the `$Seat` case: each object cell viewed from the box cell at the corner facing the block, transformed by a group element, seated one step out of the block corner its image faces; the entry's exact form. Its `$Mirror` case and its determination are one-frame.
- `3e980e27` — `parse.footprint` with `paint`, and the determination: a shape cell viewed from the marker inside its shape, stored as a Shift catalog keyed by marker color, transformed by the color's D4 element, seated at a bare marker of that color. View and seat in different rules.
- `36d67576` — `anchored` with `carried`: a mark viewed from the model part's anchor, turned by the part's pose, seated at that part's anchor. Different rules.
- `4c416de3` — `shape` with `stamp`: a stamp cell viewed from the site the whole stamp surrounds, stored as a Shift catalog keyed by corner, carried onto another corner by the D4 element mapping the corners, seated at the target site. Different rules.
- `11dc524f` — `paint`, the mirror branch: a shape cell viewed through `BoxFrame.inner` from the shape's box, flipped across the slide axis, seated by `compose` at the mirror box, a Position `jump` derives from the docked box.
- `2546ccf6` — `reflect` with `mirror`: a block-tile cell viewed through `BoxFrame.inner` from its tile's box, flipped across the cut (two flips chained for the diagonal), seated by reading the missing tile's `BoxFrame.inner` backward. Both frames are `tile_frame.margin` Positions.
- `64efde09` — `emit`: a beam source viewed through `BoxFrame.inner` from its bar's box, carried by the `D4Map` element mapping the bar onto another, seated by reading the other bar's `BoxFrame.inner` backward.
- `2c181942` — `dock_cell`: a piece cell turned in its box frame, then composed with the displacement of the turned notch cell from the seat cell, `P_seat + G(P - P_notch)`: the two-step form with the notch cell as source frame and the seat cell as target, both bound in the rule.

## Spec

No interface change: every caller binds its two frames as plain Positions already in its rules, so the inline five-argument form serves all of them, and no key or comp form is needed.

- **Seat through a frame view read backward.** `2546ccf6` and `64efde09` seat by reading the target's `BoxFrame.inner` backward, which is `compose(F_dst, V2, P_out)` restricted to the target's viewed cells; `BoxFrame.margin` places both frames, so the `Not:` clause on decomposition frames does not reach them. The Match line names that seat form beside the `Reframe.inner` view form, and a caller states the domain test itself.
- **Split view and seat.** `3e980e27`, `36d67576`, and `4c416de3` store the viewed Shift in a catalog and seat it in a later rule. A call joins the view into the seating rule, or the catalog carries the source frame as a column.
- **The Shift exclusion.** What keeps `1b60fb0c` out beside `2c181942` is that its Shift is searched over and keyed, with many origin pairs collapsing onto it, where `2c181942` binds one notch cell and one seat cell.

Survey: 2026-09-14 00:46 — the solvers since 2026-09-09 22:10.

Callers:

5545f144 `placed` — the arrow cell read from the tip's Position, turned by the quarter turn that carries its old heading onto its new one, and seated at the rest Position; the entry's inline five-argument form with both frames as plain Positions.
846bdb03 `placed` with `out` — a shape cell viewed from the shape's own bounding box, turned by a group element, and seated by reading the core region's `crop` backward; view and transform in one rule, seat in the other.
66ac4c3b `painted` — ink read from one marker line's frame, flipped on the axis the lines lie across, seated at the other marker line. Recorded at 2026-09-09 22:10.
4938f0c2 `img`, the `$Seat` case — an object cell viewed from its anchor, transformed by a group element, seated one step out of the block corner its image faces. Recorded at 2026-09-09 22:10.
3e980e27 `paint` with `parse.footprint`, and the determination's `refuted` — a shape cell viewed from the marker inside its shape, transformed by the color's D4 element, seated at a bare marker of that color. Recorded at 2026-09-09 22:10.
36d67576 `carried` with `poses` — a mark viewed from the model part's anchor, turned by the part's pose, seated at that part's anchor. Recorded at 2026-09-09 22:10.
4c416de3 `stamp` with `shape` — a stamp cell viewed from the site its shape surrounds, carried onto another corner by the D4 element mapping the corners, seated at the target site. Recorded at 2026-09-09 22:10.
11dc524f `paint`, the mirror branch — a shape cell viewed by `crop` from the shape's box, flipped across the slide axis, seated by `compose` at the mirror box. Recorded at 2026-09-09 22:10.
2546ccf6 `mirror` with `reflect` and `tile_cell` — a block-tile cell viewed by `crop` from its tile's box, flipped across the cut (two flips chained for the diagonal), seated by reading the missing tile's `tile_cell` backward. Recorded at 2026-09-09 22:10.
64efde09 `emit` with `bar_cell` — a beam source viewed from its bar's box, carried by the `D4Map` element mapping that bar onto another, seated by reading the other bar's `bar_cell` backward. Recorded at 2026-09-09 22:10.
2c181942 `dock_cell` — a piece cell turned in its box frame, then composed with the offset of the turned notch cell from the seat cell; the two-step form with the notch cell as source frame and the seat cell as target. Recorded at 2026-09-09 22:10.

Near-misses:

One frame — the rule's view and its seat bind the same Position or the same Box, which is `apply_about`: 5545f144 `sym_cell`; 981571dc `counterpart` and the determination's `mirrored`; 47996f11 `counterpart`; 4c5c2cf0 `copy` and the determination's `orbit`; 3345333e `mirror`; 2bcee788 `mirror`; 2b01abd0 `mirror`; 5b692c0f `mirror`; 538b439f `image`; 60d73be6 `image`; 6855a6e4 `image`; 88207623 `image`; 84551f4c `landed`; 90347967 `moved`; e729b7be `image`, the `$Marker` case; 7ed72f31 `image_along`; 93c31fbe `ink`; 0934a4d8 `ext_map`.

One frame read forward then backward — the transform runs inside one region's own frame, and the seat is that same frame's view read the other way: 18419cfa `paint`; 11852cab `paint`; 7468f01a `out`; 79369cc6 `image`; 7df24a62 `pose`; 7b3084d4 `image`; 4c7dc4dd `repeat`; 6ffbe589 `rot.succ`; 291dc1e1 `turned` with `placed`; 6aa20dc0 `stamp`; 845d6e51 `over`; 67e490f4 `over`.

A landing by an Offset searched over and keyed, which many origin pairs produce: 6e4f6532 `seated`; 1b60fb0c `placement` with `turn_step`; 898e7135 `congruent.observed_member`; 8e5c0c38 `mirrored`; 21897d95 `placed_arrow` and `arrow_host.item`; 0dfd9992 `pair` and `step`; 1acc24af `turned`; b7cb93ac `foot`; 412b6263 `content` and the determination's `seat.shape`; 08573cc6 `arm`.

A grid-frame transform followed by a translation that no frame pair produces: 496994bd `img`, the `$Seat` case, which flips in the grid frame and then jumps by the block's margin; 62593bfd `paint`, whose jump is a slide with no transform.

A decomposition's inner frame, which no Position places, reseated by `concat` or by a tile `crop`: 6f473927 `place`; 103eff5b `tile_col`; 5a719d11 `out` and the determination's `cand_out`; 46442a0e `out` in both cases; 0934a4d8 `out`; f25ffba3, 47c1f68c, 833dafe3, 67e8384a, 62c24649, 3af2c5a8, and 0c786b71, each in the `out` or `paint` rule that reads `params.tile_d4`.

A transform in the grid's or the canvas's own frame with nothing seated: f4081712, 9ecd008a, 929ab4e9, and 67b4a34d, each in `counterpart` and `restored`; 5751f35e `orbit_color`; 6165ea8f `slot`; bd4472b8 `fill`; 4522001f `lit` and the `$Pair` branch of `out`; 21897d95 `out` and the determination's `broken`; 291dc1e1's determination `occ.shape`.

Spec:

Two definition points come out of the sites above, and neither changes the operation's arity or its rule body.

- **The frame columns take a Box, not a cell.** The signature types both frames `Position`, and 5545f144 `placed` binds plain cells. Three callers do not: 846bdb03 views from `shape.box` and seats at `core.box`, 11dc524f views from the shape's bounding box and seats at the mirror box, and 2546ccf6 views from one tile's box and seats at another tile's box. In each the frame is a rectangle with extent, and the D4 element acts inside that rectangle's own frame, so the `Position` reading misstates what the column holds. The rule body serves both readings without change, because `relative` and `crop` return the same offset. State the two frame columns as `Box` and name the two readings in the entry.
- **The two-step clause of the Match line found only one-frame sites in this scope.** 47996f11's determination `mirrored` writes a grid-frame flip and then a `compose` with twice the candidate's offset, which is the shape that clause describes; its source frame and its target frame are the same line, so it is `apply_about` written the long way, and the same file's `counterpart` states that one-frame form directly. 2c181942 `dock_cell` stays the only two-frame site the clause reaches. The clause needs the two frames to be distinct, which the Match line's opening already demands; no edit is needed, and the note stands so the next survey does not re-derive it.

The split of the view from the seat, which the entry already records, gained one site: 846bdb03 joins `placed` to `out` on the inner coordinate, the way 2546ccf6 joins through `tile_cell`.

Reimplementations: none.

The search read the 485 solvers of the scope. 72 of them hold an `apply` atom; a clause-level parser pass over those files found 58 rules that pair an `apply` atom with a view (`relative` or `crop`) or a seat (`compose`, `crop`, a `concat` primitive, or `jump`), and each of those rules was read with the rules that feed it and the rules that read it, which is how the chains through a stored Offset and through a keyed inner-frame relation were reached.

Survey: 2026-09-14 02:38 — the solvers since 2026-09-14 00:46.

Callers:

963f59bc `copy` — each shape cell read from the shape cell the marker aligns with, reflected across the axis the two share, and seated at the marker; the entry's inline five-argument form, with `relative`, `apply`, and `compose` in one rule and both frames bound as plain cells.
5545f144 `placed` — the arrow cell read from the tip's Position, turned by the quarter turn that carries its old heading onto its new one, and seated at the rest Position. Recorded at 2026-09-14 00:46.

Negative evidence across the scope: of the 23 solvers, 9 hold a transform atom at all. A clause-level parser pass over the scope found 5 rules that pair a transform atom with a view (`relative`, `crop`) or a seat (`compose`, `crop`, a `concat` primitive, `jump`, `neighbor`), and the chains that split a view from its seat across rules were read in the 4 further files whose transform feeds another rule. Two of those sites bind two distinct frames; the rest are the near-misses below.

Near-misses:

One frame — the view and the seat bind the same Position or the same Box, which is `apply_about`: 5545f144 `sym_cell`, whose view and seat are both the tip's Position; 93c31fbe `ink` with `content_in`, whose view and seat are both the content box. Both recorded at 2026-09-14 00:46.

A landing by an Offset searched over and keyed, which many origin pairs produce: 6e4f6532 `seated`, whose Offset comes from an `Occurrences` search over poses. Recorded at 2026-09-14 00:46.

A transform on an orientation value alone, with no cell viewed and no cell seated: 93b581b8 `painted`, where `apply_diag_dir` carries the block's corner onto the copy's corner and the copy's cells are read by an `inside` test on a jumped box; 952a094c `landing` with the determination's `clash`, where `apply_diag_dir` carries a mark's corner onto the corner it ejects to and the landing cell comes from the parse.

A crop view, then the transform in the cropped frame, which is the output's own frame, with nothing seated: 94133066 `out` with `panel`, and `placed`, where the panel is cropped from its bounding box and the D4 element acts in that frame to give the output cell directly.

A seat with no transform: 85b81ff1 `moved`, which displaces an object by the offset of one bounding box from another; 4c3d4a41 `placed` in the `$Rigid()` case, which displaces contents by the offset of their low end from the seat; 95990924 `painted` in the `$Stamp()` case, whose seat is an `Occurrences` offset over a stored picture; 963c33f8 `landed` and 84ba50d3 `landed` with `through`, whose seats are slide offsets; 94be5b80 `ink`, whose seat is a `jump_offset` along the stack; 8abad3cf `paint`, which composes a place in a row box onto a line Position.

A decomposition's inner frame, which no Position places: 4e7e0eb9 `field_cell`, and 7491f3cf `parse.panel_view`, 8a6d367c `hole_view` with `pattern_cell`, and 94414823 `placed`, each a `crop` view with nothing transformed. 4e7e0eb9 recorded at 2026-09-09 22:10.

Spec:

No change to the interface or the definition comes out of this scope.

- **The frame columns.** 963f59bc `copy` binds two plain cells, as 5545f144 `placed` does. The `Box` typing proposed at 2026-09-14 00:46 takes no counter-evidence from this scope, because a Box column serves a cell frame without a change to the rule body: `relative` returns the same offset from a cell as from a box.
- **A searched frame pair is still a call.** 963f59bc searches over frame pairs: `anchor` joins each marker to every shape cell that shares a line with it, and `copy` runs the view, the transform, and the seat once per pair, with the grid test filtering the result. The exclusion that keeps 6e4f6532 `seated` out rests on the Offset being the searched object, with many origin pairs collapsing onto it, so it does not reach a site that searches the two frames themselves. The entry's Shift exclusion already states this; 963f59bc is a second site under it.
- **The direction-only class.** 93b581b8 and 952a094c apply a D4 element to a corner and never view or seat a cell. Neither the Match line nor the grep signature reaches them, because both demand a transform of a cell offset, so the `Not:` line needs no new clause. The note stands so the next survey does not re-derive it.

Reimplementations: none.

The search read the 23 solvers of the scope: a grep for the entry's signature over each file, then a clause-level parser pass that tagged every rule by whether it holds a transform atom, a view atom, and a seat atom, which produced 5 rules across 5 files; each of those rules was read with the rules that feed it and the rules that read it.
