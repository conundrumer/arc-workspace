# `apply_about` — a D4 transform taken about a placed frame

The image of a cell under a D4 element, taken about the frame that a Position places, rather than about the grid: the cell is read in that frame, transformed there, and seated back. `apply` is this with the grid's own frame, so a solver whose transform turns about an object — a marker, a bounding box, a stamp seat — states its hypothesis in the same vocabulary instead of unfolding the view and the seating around it. The frame Position needs no relation to the cell: a cell outside it reflects across the frame's center lines just as an inside cell does, which is what a solver copying content around a pivot reads.

```
.decl apply_about(d: D4, p_frame: Position, p: Position, p_out: Position) inline
apply_about(D, F, P, P_out) :-
    displacement(F, P, V), apply(D, V, V2), compose(F, V2, P_out).
```

Not: `apply` (about the grid's frame); `Reframe` (the view alone, with no transform); a seat with no transform (`displacement` and `compose` around a stored offset, as a stamp placement reads); a transform whose landing is a Shift no origin produces, such as a searched placement offset; `D4Map` (which tests a transform over a cell set and reports the element, not a cell's image).

Match: a rule that binds one Position F and holds all three of `displacement(F, P, V)` — or a `Reframe.inner` whose `outer` is F — `apply(D, V, V2)`, and `compose(F, V2, P_out)`, in either compose argument order. Grep signature: files holding both `displacement` (or `.inner`) and `apply(` and `compose(`; `grep -n 'displacement\|\.inner\|apply(\|compose(' programs/solvers/*.dl` then read the rules that hold all three.

Survey: 2026-09-08 20:07

The full-corpus pass ran at 2026-09-08 02:12. The pass at the time above covered only the solvers edited since it, and found no new caller.

Survey: 2026-09-08 22:06, over the solvers at or after the previous survey's time

That pass read the twenty-six solvers whose file time is at or after 20:07. It found no caller beyond `538b439f`, whose form the entry already records, and no near-miss outside the classes the `Not:` line names.

Survey: 2026-09-08 22:28, over the solvers at or after the previous survey's time

That pass read the five solvers whose file time is at or after 22:06. It found no caller: none of them names a D4 element or takes a cell's image under one. Its one near-miss, `5587a8d0`'s seat of a ring offset at a stored center, falls in the seat-with-no-transform class the `Not:` line names.

Survey: 2026-09-09 02:34, over the solvers at or after the previous survey's time

That pass read the thirty-three solvers whose file time is at or after 22:28, by the grep signature and by a parser pass over rules holding an `apply*` atom with a view and a seat. Eleven rules in scope hold an `apply*` atom. Six reach the full shape, and all but the new caller below sit in files the entry already records. No file in scope reaches the shape through a `Reframe.inner` or a `BoxFrame.inner` read: every `.inner` site in scope that seats carries no transform.

Survey: 2026-09-09 05:20, over the solvers at or after the previous survey's time

That pass read the twenty-two solvers whose file time is at or after 02:34, by the grep signature and by a scan for any D4 token at all. It found no caller: outside `5b692c0f`, whose form the entry already records, no file in scope names a D4 element or takes a cell's image under one. Eleven of them hold a view or a seat with no transform. Its three near-misses — `5dbc8537`, `5b526a93`, `5c2c9af4` — all seat a view or a stored offset with no transform, the class the `Not:` line names.

Survey: 2026-09-09 14:24, over the solvers at or after the previous survey's time

That pass read the eleven solvers whose file time is at or after 05:20, by the grep signature and by a parser pass over rules holding a view, an `apply*` atom, and a seat. It found no caller beyond `4c5c2cf0`, the surfacing solver. Four of them name a D4 element, and five rules in scope hold an `apply*` atom; only the two rules of `4c5c2cf0` reach the full shape. No rule in scope reaches it through a `Reframe.inner` or a `BoxFrame.inner` read. The forms the entry records for `b7cb93ac`, `4e7e0eb9`, and `4c416de3` still match. Its two further near-misses — `4e34c42c` and `045e512c` — seat a searched Shift or a step delta with no transform, the class the `Not:` line names.

Survey: 2026-09-09 22:57, over the solvers at or after the previous survey's time

That pass read the 307 solvers whose file time is at or after 14:24 (a corpus-wide file-time bump put most of the corpus in scope), by the grep signature, by a scan for any D4 token, and by a parser pass over rules holding an `apply*` atom with a view and a seat. It found no caller beyond `6855a6e4`, the surfacing solver: every rule in scope that reaches the full shape sits in a file the entry already records, and their forms still match. Its new near-misses all fall in classes the `Not:` line names. `66ac4c3b` reflects each mark from one marker line to the other — a view at one line, a flip, a seat at the other line — and its concept is a reflection across the midline between them, which is one Position only when the line spacing is odd; it stands beside `2546ccf6` as pressure on the two-frame exclusion, and `apply_between.md` holds it. `64efde09` carries a cell from one bar's box to another's (two-frame transfer); `67e490f4` and `62593bfd` transform in a box view with nothing seated back; `6165ea8f`, `5751f35e`, and `412b6263` transform about the grid's or a decomposition's frame; `1acc24af`, `142ca369`, and `269e22fb` land by a searched `Occurrences` placement; `44d8ac46` and `44f52bb0` test elements through `D4Map`. No reimplementation of a lib primitive was found in scope.

Survey: 2026-09-10 06:40, over the solvers at or after the previous survey's time

That pass read the 370 solvers whose file time is at or after 22:57 (another corpus-wide file-time bump), by the grep signature, by a scan for any D4 token, and by a parser pass over rules holding an `apply*` atom with a view and a seat. It found no caller beyond `7ed72f31`, the surfacing solver: every rule in scope that reaches the full shape sits in a file the entry already records, and their forms still match. Its new near-misses all fall in classes the `Not:` line names. `79369cc6`, `7df24a62`, `7b3084d4`, and `6e4f6532` land a turned figure by a searched `Occurrences` placement; `6aa20dc0`, `6f473927`, and `760b3cac` transform in a decomposition's frame, `760b3cac` a reflection across an abutting tile edge that lies between two cell lines and so no cell Position places; `6ffbe589` turns about the crop's own frame with nothing seated back; `72ca375d` and `73ccf9c2` compare a stored element through `D4Map`. `5545f144`'s `placed` rule views at the tip and seats at the rest — the two-frame transfer `apply_between.md` holds — beside its recorded `sym_cell` call. No reimplementation of a lib primitive was found in scope.

Survey: 2026-09-10 08:21, over the solvers at or after the previous survey's time

That pass read the 385 solvers whose file time is at or after 06:40 (another corpus-wide file-time bump), by the grep signature, by a scan for any D4 token, by a parser pass over rules holding an `apply*` atom with a view (`displacement`, or a `Reframe`/`BoxFrame` `.inner` or `.view` read) or a seat, and by a parser pass for the D4-free half turn (`displacement(P, F, V), compose(F, V, Q)`). It found no caller beyond `84551f4c`, the surfacing solver: every rule in scope that reaches the full shape sits in a file the entry already records, and their forms still match, the view-seating forms of `3345333e` and `18419cfa` and the D4-free half turns of `4290ef0e` and `50c07299` included. The five D4-naming files in scope the entry does not record take no cell's image: `212895b5`, `46c35fc7`, `7e2bad24`, and `1e5d6875` turn a heading or a step direction by `apply_dir`, `apply_dir8`, or `apply_diag_dir` (a walk's gait, a beam's reflection off a wall, a piece color's rotation), and `80214e03` transforms a tile index about the arrangement's own frame, which plain `apply` states. The D4-free pass's other hits (`16de56c4`, `1b59e163`, `20981f0e`, `20fb2937`, `31aa019c`, `363442ee`, `3f23242b`, `4258a5f9`, `4c3d4a41`, `5117e062`, `522fdd07`, `652646ff`, `8403a5d5`) all carry a displacement between two cells onto a third with no transform, the seat-with-no-transform class the `Not:` line names. No near-miss outside the `Not:` line's classes, no spec question, and no reimplementation of a lib primitive was found in scope.

## Callers

- `4938f0c2` — program and determination, about the marker block's box; the entry's exact form.
- `90347967` — every grid cell about the marker cell.
- `e729b7be` — every input cell about the crossing cell.
- `981571dc` — program and determination: the counterpart about the wallpaper center, seated through a `Reframe` read backward, and the same operation about a candidate center, written as the grid-frame flip plus twice the center offset.
- `47996f11` — the same two forms, program and determination.
- `3345333e` — every grid cell about each candidate mirror frame.
- `11852cab` — the figure in its bounding box, seated back through the same view.
- `18419cfa` — each interior's ink in that interior's box.
- `4290ef0e` — the operation at a fixed half turn, with no D4 element named in the file.
- `4c5c2cf0` — program and determination; the surfacing solver.
- `50c07299` — a fixed half turn about the cell just past a segment's end, with no D4 element named in the file.
- `2bcee788` — the shape about the two-line box each of its mirror cases bounds.
- `2b01abd0` — the figure about a cell of the divider line, by the flip of the line's perpendicular axis; the entry's exact form. Any line cell serves as the frame, since the flip fixes the along-axis.
- `538b439f` — each rectangle cell about the divider's line, by the flip of the axis that line cuts; the entry's exact form. The frame is the line's own axis-only Position, which the line detection already holds.
- `5545f144` — each drawn cell about a candidate tip cell, by the flip of the axis perpendicular to the tip's heading; the entry's exact form. The image is tested for membership in the same figure, so the rule states its domain through that test.
- `5b692c0f` — each cell of an object's box about that object's mark line, by the flip of the axis that line cuts; the entry's exact form. The frame is the axis's own line Position, and the rule states its domain itself.
- `60d73be6` — each mark about either line of a divider cross, by the flip of the axis that line cuts, the two flips closed over; the entry's exact form. The frame is each line's own axis-only Position, and the rule states its own domain test.
- `6855a6e4` — each mover cell about the mirror cell its cast halts on (a `Ray.stop` cell), by the flip of the cast's axis; the entry's exact form. The frame is a cell in the mover's own line, and the image's domain test is left to the `out` rule's grid join.
- `84551f4c` — each cell of a toppling bar about the bar's base cell, by the quarter turn of the stored topple sense; the entry's exact form. The image's domain test is left to the `out` rule's grid join.
- `7ed72f31` — each shape cell's along coordinate about its object's mirror line, per axis on which the mirror is thin, by that axis's flip; the entry's exact form. The frame is the mirror's axis-only line Position, a point mirror giving one on each axis, and the image's domain test is left to the `out` rule's grid join.
- `88207623` — each shape cell about a cell of the line segment it leans on, by the flip of the stored axis across the line; the entry's exact form. Any cell of the segment serves as the frame, and the rule states its own domain test.

Five of those callers seat by reading a frame view backward, and so inherit a domain test from the view comp's `cell` set. `apply_about` emits an image with no domain, so each of them states the test itself (`in(P_out, _)`).

## Near-misses

- Two-frame transfer — view from one frame, transform, seat in another: `4938f0c2`'s `$Seat` case, `3e980e27`, `36d67576`, `4c416de3`, `11dc524f`, `2c181942`, `0e206a2e`, `2546ccf6` (a mirror across a `DividerFrame` cut, where the tiles need not share an extent). One frame Position cannot state it. `apply_between.md` holds that operation.
- The line stated as an offset — a grid-frame flip, then a `jump` or a searched Shift: `1b60fb0c`, `3631a71a` with its twin `af22c60d`, `496994bd`, `50f325b5`, `b7cb93ac` (footprint turned in its box, seated at a searched `Occurrences` placement), `0dfd9992` (a point-group element plus a searched lattice shift — a glide has no fixed point), `08573cc6` (a rotated Shift no cell's displacement produces). There is no frame Position to pass.
- The frame is a decomposition's, and no Position places it — per-axis flips of a tile position, glued by `compose`: `4e7e0eb9`; a transform in the intile frame of `divide_2d`, reseated by `concat_2d`: `47c1f68c`; the flip of a `DividerFrame` panel position, which picks the panel paired with it across the arrangement: `5a719d11`. The tile-arrangement solvers instantiate the same class: the transform in a `divide` inner frame, reseated by `concat`. `5a719d11` is the simplest member: the arrangement's own origin frames the transform, so plain `apply` states it, with no view and no seat to fold.
- A view seated at another Position with no transform — a stored or derived figure, offset, or footprint carried to a target: `247ef758`, `3befdf3e`, `3f23242b`, `5117e062`, `4c177718`, `5168d44c`, `4acc7107`, `14754a24`, `363442ee`, `414297c0`, `48d8fb45`.
- The D4 element labels a stored pose, compared as a set — no cell's image is taken: `4c177718`, `3a25b0d8`, `3d588dc9`, `409aa875` (through `D4Map`), `3aa6fb7a` (a RIGID pose, composed onto a searched `Occurrences` placement).
- The box selects, and does not frame — a `Bbox` says which cells transform, and the transform itself is about the grid's or a panel's own frame: `2697da3f`, `4c7dc4dd`, `67b4a34d` with its family. `apply` states it.
- Nothing seated back — the transform's output is the crop's own frame (`7468f01a`); an extent-changing Inset with the transform about the mosaic's frame (`0934a4d8`); a repeated displacement that coincides with a half turn but holds no D4 element (`2ccd9fef`); a turned inner position read as a tile index (`103eff5b`); a transform inside a `BoxFrame` crop whose output is that crop's own frame (`291dc1e1`); a chain reversed by pairing `Order.rank` against `Order.rank_desc` (`5792cb4d`), which is a reflection recovered from step indices along a path that bends, so no D4 element and no frame Position realize it.

## Spec

No change to the interface or the definition. The four-argument inline form serves every caller as written: each binds its frame as a plain Position already in the rule — a `Bbox.margin`, a `BoxFrame.margin`, a marker cell, a stored center, a candidate frame from a keyed relation — so the operation needs no key parameter and no comp form. `3345333e` is the strongest evidence for the inline form: its frame varies per row from a relation, and it pays for a `Reframe<Position>` instance solely to unfold the operation. `4290ef0e` and `50c07299` would have to source a D4 element their models never name; whether those sites state a transform at all is a question for their models, not for the signature.

The `Not:` line now excludes a landing by Shift rather than every rule that writes a doubling. `D(P) + 2*Delta` is `apply_about(D, Delta, P)` whenever `Delta` lies on the flipped axis, which is how the determination sites of `47996f11` and `981571dc` reach their candidate center — each has in hand the origin its transform turns about, and each passes that same origin to a `Reframe.outer` in its program. `50f325b5` searches an `Occurrences` placement Shift that no origin produces, and stays out. Those frame arguments are Shift-typed, an offset from the grid center rather than a frame cell; `Shift = Position` in lib, so the declared `p_frame: Position` accepts them.

`7ed72f31` passes an axis-only along component from `split` as the operand, not a full cell; `apply` and `compose` act pointwise, so the form covers it with no change.

`5b692c0f` is the third caller whose frame is an axis-only line Position that the flip fixes, so the "any line cell serves" reading recorded for `2b01abd0` is a stable form. It also states its own domain test without reading a view comp, which extends that behavior beyond the view-seating callers.

The full-corpus re-survey confirms the exclusions: `0dfd9992` and `08573cc6` stand beside `50f325b5` as landings by a Shift no origin produces, and `2546ccf6` is the strongest pressure on the two-frame exclusion — its concept is a mirror in the cut, and only its unequal tiles keep it out.

Survey: 2026-09-10 19:51 — the solvers since 2026-09-10 08:21.

**Survey of `apply_about` — a D4 transform taken about a placed frame — over the 48 solvers in scope.** The pass used the grep signature (files holding a view — `displacement`, or a `.inner`/`.view` read — plus `apply(` plus `compose(`), a scan for any D4 token (`D4`, `apply*`, `d4_*`, `flip_of`, `rotation(`, `sym_member`), and a parser pass (`.scratch/surveys/apply_about/2026-09-10-195158/match.py`) over rules holding an `apply*` atom, recording which view and seat atoms share the rule, and over the D4-free half turn (`displacement(P, F, V), compose(F, V, Q)`).

1. Callers

Callers:
- `88207623`, `image` — each shape cell about a cell of the line segment it leans on, by the flip of the stored across axis: `displacement(L, P, V), apply(F, V, V2), compose(L, V2, Q)`, then `in(Q, _)` as its own domain test. The entry already records it; its form still matches.

No second caller. Fourteen files in scope name a D4 element; sixteen rules in scope hold an `apply*` atom. The grep signature matched four files (`11dc524f`, `2c181942`, `88207623`, `b7cb93ac`), and only `88207623`'s rule holds all three of view, transform, and seat about one frame. The D4-free half-turn pass matched no rule in scope. No rule in scope reaches the shape through a `Reframe.inner` or `BoxFrame.inner` read seated back at the same frame.

2. Near-misses

- `846bdb03`, `placed` with `out` — the shape is viewed in its own `BoxFrame` (`shape.inner`), transformed there, and seated into the crop's interior box (`interior.inner` read backward). Two frames, the shape's box and the interior's box, so one frame Position cannot state it: the two-frame transfer `apply_between.md` holds. The seat is also the crop's own frame, the nothing-seated-back class.
- `2c181942`, `dock_cell` — the piece is turned about the grid's frame and lands by the Shift `displacement(P_turned_notch, P_seat, V)`, a displacement between a turned notch cell and a seat cell. The landing is a Shift no origin produces, and the view (`box.inner`) and the seat are in different frames: the two-frame transfer class, as the entry records.
- `11dc524f`, `paint` — the shape is viewed in its box (`box.inner`), flipped, and seated at `mirror`, a cell `jump`ed from `home`. View at the box, seat at another Position: the two-frame transfer class, as the entry records.
- `b7cb93ac`, `foot` — each piece's shape is turned about the grid's frame and later lands by a searched `Occurrences` placement. No frame Position to pass, as the entry records.
- `0dfd9992`, `cand`, `pair`, `step` — a point-group element about the grid's frame plus a lattice Shift; a glide has no fixed point. The landing-by-Shift class, as the entry records.
- `08573cc6`, `arm` — a rotation applied to a Shift (`apply(M, Delta, DeltaR)`) that no cell's displacement produces, then `compose` onto the arm's end. Landing by Shift, as the entry records.
- `291dc1e1`, `turned` and the determination's `occ.shape` — a transform in the crop's intile frame with nothing seated back (the program) and a landing by `Occurrences` (the determination). As the entry records.
- `412b6263`, `content` and the determination's `seat.shape` — the input transformed about its own frame; plain `apply` states it. As the entry records.
- `142ca369`, `occ.cell` — D4 closed over a searched `Occurrences` placement; no cell's image about a frame. As the entry records.
- `409aa875`, `same` (`D4Map`) and `placed` — the D4 element labels a stored pose compared as a set. As the entry records.
- `44f52bb0`, `d4` (`D4Map`) and `group` — the element is tested through `D4Map` and `sym_member`; no cell's image is taken. As the entry records.
- `212895b5`, two `apply_dir` sites, and `85fa5666`, `source` (`apply_diag_dir`) — a heading or a corner label is turned; no cell's image is taken. `212895b5` is the class the entry records; `85fa5666` joins it.
- Seat with no transform — a displacement carried onto a third cell, or a view seated elsewhere with no transform: `045e512c` and `20981f0e` (as the entry records), `264363fd` (`travel`, `carried`: a template carried to each marker), `7c66cb00` (`displacement(P, Q, Delta)` between a shape's leading cell and its band's far edge), `85b81ff1` (`moved`: box to box, `displacement(B_src, B_dst, V), compose(P, V, P_out)`), `05f2a901` and `84ba50d3` (`compose` of a footprint with a `jump_delta` Shift, under `Slide`). The view-only files `1478ab18`, `1a6449f1`, `868de0fa`, `8698868d`, and `8731374e` read a `.inner` with no transform and no seat.

3. Spec

No change to the interface or the definition. The one caller in scope, `88207623`, binds its frame as a plain Position already in the rule and states its own domain test, which is the form the entry records for the line-Position callers (`2b01abd0`, `538b439f`, `5b692c0f`). The near-misses fall in the classes the `Not:` line names; `846bdb03` adds one more two-frame site (shape box to interior box) beside `4938f0c2`'s `$Seat` case and `291dc1e1`, so the pressure on the two-frame exclusion rests with `apply_between.md`, not with this entry. No signal in scope rests on a site that would call the operation and does not yet fit the four-argument inline form.

4. Reimplementations

Reimplementations: none.
