# `Obstruct<Key>` — the seats at which a footprint meets an obstacle set

The candidate seats of a footprint at which some member of the footprint, composed at the seat, lands on an obstacle cell, per key — and their complement, the seats the footprint sits clear at. The seats, the footprint, and the obstacles are all inputs, so a seat may be a placement an `Occurrences` found, a displacement a slide walks, or a grid cell, and the obstacle may be a color's cells, another object, or a stored region. Absence is tolerated: a member landing off the frame meets no obstacle, which is what a stamp clipped by the grid edge or a slide leaving the frame needs.

```
.comp Obstruct<Key> {
    // The candidate seats, per key. Positions or Offsets.
    .decl seat(key: Key, m: Position)  // input

    // The footprint's members, per key, in the frame the seat composes with.
    .decl foot(key: Key, s: Position)  // input

    // The cells the footprint may not cover, per key.
    .decl obstacle(key: Key, p: Position)  // input

    // A seat at which some member lands on an obstacle.
    .decl obstructed(key: Key, m: Position)
    obstructed(Ky, M) :- seat(Ky, M), foot(Ky, S), compose(M, S, P), obstacle(Ky, P).

    // A seat at which every member lands clear.
    .decl clear(key: Key, m: Position)
    clear(Ky, M) :- seat(Ky, M), !obstructed(Ky, M).
}
```

Not: `Occurrences.mismatch` (a member off its value or off the frame refutes; here only an obstacle refutes, and off-frame is silent); `Slide.rim_dir` (a point mover's next step, no footprint); `Ray.blocked` (a cast's blocked cells, no footprint); a contact test between two footprints both placed (the pair conflict of `PlacementPruning`).

Match: a rule whose body composes each member of a footprint set at a candidate seat and joins the landed cell with a second cell set, deriving the seat (and its key), where a consumer negates that rule's head — including the form whose seat set is implicit (every cell of the grid, or every displacement of a `shift` domain) and the form whose landed-cell test is a negated membership in a free set. Grep: `compose(` beside a negated head in a `Slide.node`, `Ray.blocked`, or output rule; `obstructed`, `covering`, `blocked`, `halted`. Match with the parser.

Survey: 2026-09-10 04:32

Callers: 79369cc6 (surfacing, `blocked`: seats are `Occurrences` placements keyed by D4, the footprint is the image's fill cells, the obstacle is the mark cells), 05f2a901 (`covering`, keyed by Choice: seat = `shift` domain, footprint = `shape`, obstacle = `blocked`; feeds `slide.node`), 11dc524f (`covering`: seat = `shift`, footprint = the shape's box cells, obstacle = the block's box cells; feeds `slide.node`), 17829a00 (`covering`, keyed by object Ident: seat = `shift`, obstacle = `border_cell`; feeds `slide.node`), 56dc2b01 (`covering`: seat = `shift`, footprint = `mover_cell`, obstacle = `anchor_cell`; feeds `slide.node`), 5168d44c (`obstructed`: seat = every grid cell, footprint = the stored ring, obstacle = `dot_cell`; its negation feeds `cast.blocked`), 14754a24 (`blocked`, keyed by Footprint: seat = every grid cell, footprint clipped to the frame, obstacle = the negated free set), 16b78196 (`sunk`, keyed by (host, piece, dir): seat = the probed `rest` offsets, obstacle = the host's cells), 1acc24af (`unreached`, via `placed`: seat = `seat.placement` keyed by Turn, obstacle = the cells outside `access`), 446ef5d2 (`spills`, via `place`: seat = `occ.occurrence`, footprint = the piece's drawn-colored cells, obstacle = the rectangle's edge cells), 25094a63 (`Determine.refuted`: seat = `occ.occurrence` keyed by (example, side, color), obstacle = the cells the output kept; the head projects the seat away to the side), 1e5d6875 (`Determine.off_step`, via `copy_land`: seat = one unit step per DiagDir, footprint clipped to the frame, obstacle = the cells the output did not repaint). No `// family:` sibling points at any of these.

Near: `Occurrences<Key, Unit>` with the free set as `cell`, where a member off the frame must refute (332f06d7 `fits`, 6e453dd6 `fits`, 6a1e5592 `occ`, 184a9768 `occ`, 5dbc8537 `occ`, 681b3aeb `occ`, b7cb93ac `occ`, 6cf79266 `occ`, 446ef5d2 `occ`, 1acc24af `seat`); an obstacle that is absence from the frame (337b420f `clash`, 642d658d `Determine.off_grid`); valued matches, where the obstacle depends on a member's or the seat's color (4c3d4a41 `refuted_shift`, 3e980e27 `Determine.refuted`, 20fb2937 `Determine.missed`, 3f23242b `Determine.missed`, 10fcaaa3 `Determine.mismatch`, 4e34c42c `disagree`); a footprint reaching its landing by a recursive scaled walk with no compose to feed (447fd412 `astray`); coverage universals, refuted by a target cell no member covers (1acc24af `uncovered`, 6e4f6532 `partial`, 20270e3b `open`, 3345333e `upheld`); a head that also carries the landed cell, which a consumer reads (16b78196 `gap`); point movers stepping by `neighbor` under a negated head, the `Slide.rim_dir` / `Rim` exclusion (about 60 rules, e.g. 54d82841 `walled`, 2c608aff `block`, d9fac9be `defect`); clip-to-grid stamps whose negated head is only the output fallback, deriving the landed cell and rejecting no seat (about 70 rules, e.g. 0ca9ddb6 `painted`, 3ac3eb23 `lit`).

Spec, from the callers: seats arrive as a shift domain, the grid, `Occurrences` placements, probed rest offsets, or a unit step; keys carry Choice, D4, Ident tuples, or Footprint; the negated-free-set obstacle form works where the caller clips its footprint to the frame first, so off-frame silence changes nothing. Spec question: when does a caller pick `Obstruct` over `Occurrences` with the free set as `cell`? The sites suggest an explicit seat set (a `shift` domain, a rest offset, a grid cell) or a footprint that may hang off the frame. A witness column on `obstructed` (the landed cell) rests on 16b78196 `gap` alone, so it stays caller-only.

Survey: 2026-09-10 04:43 — the solvers modified after the survey above (4c3d4a41, 78e78cff, 794b24be, 79fb03f4, 7acdf6d3)

Callers: none.

Near: a clip-to-grid stamp whose negated head is only the output fallback (4c3d4a41 `placed`); a compose with no obstacle test (4c3d4a41 `comb`, `stage`); the `Occurrences.mismatch` reading (4c3d4a41 `Determine.refuted_shift`, now an `Occurrences<Example, Color>`); point casts fed to `Ray.blocked` (78e78cff `leak.blocked`, `cross.blocked`); a single-cell test (79fb03f4 `enterable`); a coverage universal stated positively, member by member (79fb03f4 `through` with `pass`).

Spec, from the scope: 79fb03f4 `through` has an obstacle set defined through the clearance of other seats, recursive with the seat's own clearance. `clear` negates `obstructed`, so that obstacle set would not stratify; the solver writes the universal positively over its explicit footprint. `Obstruct` serves obstacle sets fixed before the seats are judged. On the spec question, 4c3d4a41 `Determine.refuted_shift` went to `Occurrences`: a valued footprint whose off-frame members must refute.
