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

A valued caller joins its value relation on `p`. A box of even extent has no centered cell, so it seats nothing. Clipping stays at the call site: three callers clip with `in(P, _)`, one clips later against a region, and one does not clip.

Not: `GRID_STAMP` (a stored stamp whose anchor is a marked cell of the picture, reduced to offsets at expansion); `Reframe` (a cell read as a displacement from an outer origin, with no center); `BoxFrame.inner` with `centered` (the center cell alone, with no seating); `apply_about` (a D4 transform taken about a placed frame).

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

## Near-misses

- 39e1d7f9 `seat($Center())`, 20981f0e `place($Center())` — the center is one peer seat among several cases, and the composition that seats the content is shared across them. 20981f0e's `centered` tests a box margin, not a cell.
- 4290ef0e `mirror`, 11e1fe23 `mini` — the anchor is the set's own center, so nothing is seated.
- 0ca9ddb6, 0962bcdd, 3ac3eb23, 4258a5f9, d364b489, dc1df850 — the seat is a stored parameter or a marker color inside a stored grid (`GRID_STAMP`).
- d9fac9be — a frame's center cell composed with an `Occurrences` placement: one cell at a placement, no offset set.
- Center cell alone, no seating: 41e4d17e, 22806e14, 272f95fa, ce22a75a, 252143c9, 27a28665, ca8de6ea, c48954c1, 4e45f183.
