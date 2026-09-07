# `apply_about` — a D4 transform taken about a placed frame

The image of a cell under a D4 element, taken about the frame that a Position places, rather than about the grid: the cell is read in that frame, transformed there, and seated back. `apply` is this with the grid's own frame, so a solver whose transform turns about an object — a marker, a bounding box, a stamp seat — states its claim in the same vocabulary instead of unfolding the view and the seating around it. The frame Position needs no relation to the cell: a cell outside it reflects across the frame's center lines just as an inside cell does, which is what a solver copying content around a pivot reads.

```
.decl apply_about(d: D4, p_frame: Position, p: Position, p_out: Position) inline
apply_about(D, F, P, P_out) :-
    displacement(F, P, V), apply(D, V, V2), compose(F, V2, P_out).
```

Not: `apply` (about the grid's frame); `Reframe` (the view alone, with no transform); a seat with no transform (`displacement` and `compose` around a stored offset, as a stamp placement reads); a transform whose landing is a Shift no origin produces, such as a searched placement offset; `D4Map` (which tests a transform over a cell set and reports the element, not a cell's image).

Match: a rule that binds one Position F and holds all three of `displacement(F, P, V)` — or a `Reframe.inner` whose `outer` is F — `apply(D, V, V2)`, and `compose(F, V2, P_out)`, in either compose argument order. Grep signature: files holding both `displacement` (or `.inner`) and `apply(` and `compose(`; `grep -n 'displacement\|\.inner\|apply(\|compose(' programs/solvers/*.dl` then read the rules that hold all three.

Survey: 2026-09-03 21:02

## Callers

- `4938f0c2` — body and Fit, about the marker block's box; the entry's exact form.
- `90347967` — every grid cell about the marker cell.
- `e729b7be` — every input cell about the crossing cell.
- `981571dc` — body and Fit: the counterpart about the wallpaper center, seated through a `Reframe` read backward, and the same operation about a candidate center, written as the grid-frame flip plus twice the center offset.
- `47996f11` — the same two forms, body and Fit.
- `3345333e` — every grid cell about each candidate mirror frame.
- `11852cab` — the figure in its bounding box, seated back through the same view.
- `18419cfa` — each interior's ink in that interior's box.
- `4290ef0e` — the operation at a fixed half turn, with no D4 element named in the file.
- `4c5c2cf0` — body and Fit; the surfacing solver.
- `50c07299` — a fixed half turn about the cell just past a segment's end, with no D4 element named in the file.
- `2bcee788` — the shape about the two-line box each of its mirror cases bounds.

Five of those callers seat by reading a frame view backward, and so inherit a domain test from the view comp's `cell` set. `apply_about` emits an image with no domain, so each of them states the test itself (`in(P_out, _)`).

## Near-misses

- Two-frame transfer — view from one frame, transform, seat in another: `4938f0c2`'s `$Seat` case, `3e980e27`, `36d67576`, `4c416de3`, `11dc524f`, `2c181942`, `0e206a2e`. One frame Position cannot state it.
- The line stated as an offset — a grid-frame flip, then a `jump` or a searched Shift: `1b60fb0c`, `3631a71a` with its twin `af22c60d`, `496994bd`, `50f325b5`. There is no frame Position to pass.
- The frame is a decomposition's, and no Position places it — per-axis flips of a tile position, glued by `compose`: `4e7e0eb9`; a transform in the intile frame of `divide_2d`, reseated by `concat_2d`: `47c1f68c`.
- A view seated at another Position with no transform — a stored or derived figure, offset, or footprint carried to a target: `247ef758`, `3befdf3e`, `3f23242b`, `5117e062`, `4c177718`, `5168d44c`, `4acc7107`, `14754a24`.
- The D4 element labels a stored pose, compared as a set — no cell's image is taken: `4c177718`, `3a25b0d8`, `3d588dc9`.
- The box selects, and does not frame — a `Bbox` says which cells transform, and the transform itself is about the grid's or a panel's own frame: `2697da3f`, `4c7dc4dd`. `apply` states it.
- Nothing seated back — the transform's output is the crop's own frame (`7468f01a`); an extent-changing Inset with the transform about the mosaic's frame (`0934a4d8`); a repeated displacement that coincides with a half turn but holds no D4 element (`2ccd9fef`).

## Spec

No change to the interface or the definition. The four-argument inline form serves every caller as written: each binds its frame as a plain Position already in the rule — a `Bbox.margin`, a `BoxFrame.margin`, a marker cell, a stored center, a candidate frame from a keyed relation — so the operation needs no key parameter and no comp form. `3345333e` is the strongest evidence for the inline form: its frame varies per row from a relation, and it pays for a `Reframe<Position>` instance solely to unfold the operation. `4290ef0e` and `50c07299` would have to source a D4 element their models never name; whether those sites state a transform at all is a question for their models, not for the signature.

The `Not:` line now excludes a landing by Shift rather than every rule that writes a doubling. `D(P) + 2*Delta` is `apply_about(D, Delta, P)` whenever `Delta` lies on the flipped axis, which is how the Fit sites of `47996f11` and `981571dc` reach their candidate center — each has in hand the origin its transform turns about, and each passes that same origin to a `Reframe.outer` in its body. `50f325b5` searches an `Occurrences` placement Shift that no origin produces, and stays out. Those frame arguments are Shift-typed, an offset from the grid center rather than a frame cell; `Shift = Position` in lib, so the declared `p_frame: Position` accepts them.
