# `SeatCenter<Key>` — a cell set seated by its own center

Each cell of a keyed cell set paired with where it lands when the center of the set's bounding box is put on a per-key anchor. A solver placing content about a point — a window of a stored extent, a stored pattern, a redrawn block — states the seat in one atom, in place of picking the center out of the frame, reading every cell as a displacement from it, and composing that displacement at the anchor.

```
.comp SeatCenter<Key> {
    // The content, per key.
    .decl cell(key: Key, p: Position)  // input

    // The frame the content sits in, per key. A dense set needs none: its
    // box holds only its own cells.
    .decl grid(key: Key, p: Position)  // input

    // Where the center of the content's box lands, per key.
    .decl anchor(key: Key, p: Position)  // input

    .init box = BoxFrame<Key>
    box.cell(K, P) :- cell(K, P).
    box.grid(K, P) :- grid(K, P).

    // Each cell beside its seated position.
    .decl seated(key: Key, p: Position, p_seat: Position)
    seated(K, P, Q) :-
        box.inner(K, C, P_in), centered(P_in),
        cell(K, P), displacement(C, P, V),
        anchor(K, A), compose(A, V, Q).
}
```

A valued caller joins its value relation on `p`. A box of even extent has no centered cell, so it seats nothing. Clipping stays at the call site, and the runner forces it where a seat can leave the grid: an off-grid `out` cell fails the run. Three callers clip with `in(P, _)`, one clips later against a region, and one does not clip.

Not: `GRID_STAMP` (a stored stamp whose anchor is a marked cell of the picture, reduced to offsets at expansion); `Reframe` (a cell read as a displacement from an outer origin, with no center); `BoxFrame.inner` with `centered` (the center cell alone, with no seating); `apply_about` (a D4 transform taken about a placed frame); content centered in a frame through a centered Inset (the anchor is a frame and the seat an Inset between the two frames, with no center cell).

Match: a rule that takes the center of a set's frame or box under `centered`, reads the set's cells as displacements from it, and composes those at another position. The offsets come either from a `displacement` atom or from a `Reframe` whose `outer` is the centered cell. Grep for files holding `centered(`, then confirm the `compose` at an anchor.

Survey: 2026-09-05 13:41

## Spec

The center must come from the content's bounding box, not from a member of the set. 247ef758's legend shapes are hollow at the center — `247ef758 train1 input rows 0–2, cols 0–2` holds `0` at its center cell — so a center drawn from the set's own members loses those stamps. That solver already reads the center off a `BoxFrame` whose `grid` is fed. 0ca9ddb6 corroborates from outside the caller set: its stored masks are hollow at the seat their `center_pos` parameter names.

A box-derived center also lets grid-framed content in: 247ef758 and 264363fd hold their cells in the grid frame, and the comp then reads only relative offsets. 264363fd needs that, because it consumes the grid cell that carries a tip direction, not an inner position.

Taking the center as a third input instead would reduce the operation to seating by a designated cell, which is the stored-seat stamp the `Not:` line excludes. 3ac3eb23's `dot([0, 5, 1, 1])` over a 6x3 template shows that a designated seat is task data of another kind.

## Callers

- 522fdd07 — `placed`: a `Frame2D` square of the redrawn extent, seated on the center of the square it replaces.
- 5117e062 — `region($Window())`: a `Frame2D` window of the stored extent `params.win_dim`, seated on a mark.
- 363442ee — `paint($Center())`: the key panel's inked cells, seated on each mark on the canvas; the color joins on the cell column.
- 247ef758 — `off` feeding `paint`: each legend shape read as offsets through a `Reframe` whose outer is its box center, seated on every crossing of the lines its color marks.
- 264363fd — `travel` and `carried`: the loose template seated on each marker of a rectangle, keeping the source cell for the tip direction a later ray cast reads.
- 88a10436 — `seated`: the cells of the shape's box, seated on each marker cell; `content` joins the value per case, ink alone or the whole box.

## Near-misses

- 39e1d7f9 `seat($Center())`, 20981f0e `place($Center())` — the center is one peer seat among several cases, and the composition that seats the content is shared across them. 20981f0e's `centered` tests a box margin, not a cell.
- 4290ef0e `mirror`, 11e1fe23 `mini` — the anchor is the set's own center, so nothing is seated.
- 0ca9ddb6, 0962bcdd, 3ac3eb23, 4258a5f9, d364b489, dc1df850 — the seat is a stored parameter or a marker color inside a stored grid (`GRID_STAMP`).
- d9fac9be — a frame's center cell composed with an `Occurrences` placement: one cell at a placement, no offset set.
- Center cell alone, no seating: 41e4d17e, 22806e14, 272f95fa, ce22a75a, 252143c9, 27a28665, ca8de6ea, c48954c1, 4e45f183.

Survey: 2026-09-10 20:18 — the solvers since 2026-09-05 13:41.

Callers: 264363fd, 88a10436.

1. Callers — the operation is SeatCenter: a keyed cell set paired with where each cell lands when the center of the set's bounding box is put on a per-key anchor. The scope is the 371 solvers this survey was given (00576224 through ff28f65a).
   - 264363fd — `travel` and `carried`: `anchor` takes the ragged piece's box center under `box.inner` + `centered`, `travel` reads the displacement from that center to each rectangle's marker, and `carried` composes it onto every template cell; `paint` clips later against the rectangle.
   - 88a10436 — `seated`: the box center under `box.inner` + `centered`, each `box.viewed` cell as its displacement from that center, composed at each marker and clipped with `in(Q, _)`.
   - Negative evidence: across the scope, `centered(` appears in 13 solvers (11e1fe23, 20981f0e, 264363fd, 27a28665, 291dc1e1, 41e4d17e, 868de0fa, 8719f442, 88a10436, c48954c1, ca8de6ea, ce22a75a, d9fac9be); `displacement(` or a `Reframe` instance appears in 29 more. A parser pass over rules holding `compose` beside `displacement` or a Reframe read (`.scratch/surveys/SeatCenter/2026-09-10-201847/match.py`) found 12 rules; only 88a10436's takes its origin under `centered`, and 264363fd states the operation across two rules. Every other offset origin is a marker cell, a box margin, a corner, a stored seat, or a stored center. A `dist_pair(P, D, K, K)` center test appears in 7 solvers (00576224, 212895b5, 29c11459, 8d5021e8, c48954c1, d23f8c26, dce56571); none reads offsets from that center and composes them elsewhere.

2. Near-misses
   - 20981f0e `place($Center())` — `landing` enumerates the piece's displacements onto its tile and `centered(M)` tests the landed box margin; the center is one seat among peer cases (`$Slot`, `$Clear`), the seating composition is shared across them, and no center cell is taken.
   - 291dc1e1 `placed` — the turned block sits in its slab where `displacement(P_turn, P_slab, V), centered(V)`: content centered in a frame through a centered Inset, with no center cell and no anchor cell.
   - 8719f442 `seated` — the whole input frame composed with `params.seat_delta`, a uniform Inset derived from `ring_width`; the seat is stored data, and `centered(P_in)` in `$Hub` names the center cell as content, not as the seat.
   - 11e1fe23 `center` — the marks' box center under `box.inner` + `centered`; the anchor is the set's own center, so nothing is seated (`neighbor(C, Diag, P)` steps from it).
   - e729b7be `rf` (Reframe), 981571dc `view` (Reframe), 88207623 `image` — cells read as offsets from a marked crossing, a stored center Shift, or a line cell, transformed and composed back at the same origin: `apply_about`, not seating.
   - 642d658d `fp_arm`, 10fcaaa3 `stamp`/`target`, 14754a24 `footprint`, 0962bcdd, 0ca9ddb6, 3ac3eb23, a9f96cdd, b60334d2, d364b489, dc1df850 — stored offsets or a stored seat composed at a marker-colored cell: the stored-seat stamp the `Not:` line excludes.
   - 2c181942 `placed` — a designated notch cell displaced onto a seat cell and that displacement composed over the piece: seating by a designated member, not by the box center.
   - 03560426 `off`, 20270e3b `socket_rel`, 17b866bd `view`, 8731374e `crop`, 85b81ff1 `moved` — offsets from a box corner or margin, no center.
   - 137eaa0f `offset`, 90347967 `markframe`, 212895b5 `frame` — Reframe from a mark or a side's midpoint, read for geometry, composed nowhere.
   - 045e512c `fits` — displacement from an `Occurrences` placement to `ORIGIN`, a step, no center.
   - d9fac9be `out($Box())` — a frame's center cell composed with an `Occurrences` placement: one cell, no offset set.
   - Center cell alone, no seating: 27a28665, 41e4d17e, 868de0fa, c48954c1, ca8de6ea, ce22a75a.

3. Spec — the two callers read the interface as written: a box center from `BoxFrame` with `grid` fed, cell offsets from it, composition at a marker, clipping at the call site. 264363fd composes the anchor-to-mark displacement onto the cells rather than the cell offsets onto the anchor; `seated` covers both readings, so no interface change follows from it. Three near-misses (20981f0e `$Center`, 291dc1e1 `placed`, 8719f442 `seated`) center content in a frame rather than on a cell, two of them through a centered Inset between the content's frame and the target frame, which needs no center cell and holds when the extents share parity. That is a distinct operation, not a reading of this one: its anchor is a frame, and its seat is an Inset. The entry's `Not:` line could name it so the next survey classifies those sites at once. No change to SeatCenter's interface or definition follows from the sites in this scope.

4. Reimplementations: none.
