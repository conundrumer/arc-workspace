# `Runs<Key>` — maximal contiguous segments within each line of an axis

The maximal runs a keyed cell set forms along an axis: each run is a contiguous
block of the set inside one line of that axis, labeled by an opaque id. Lib
holds connectivity only over the four cardinals, so a solver that reads a
horizontal bar, a segment of a row, or a stretch of one color across a line
confines `Components` to a line by folding the line position into the node key,
and states that trick in its own comment.

```
.comp Runs<Key> {
    // The cells the runs are read over, per key.
    .decl cell(key: Key, p: Position)  // input

    // The axis the runs lie along, per key.
    .decl axis(key: Key, a: Axis)  // input

    // Keying by line confines connectivity to one line, so the perpendicular
    // steps join nothing and each component is a segment of that line.
    .type _KL = [key: Key, line: Position]

    .init _comps = Components<_KL>
    _comps.node([K, L], P) :- cell(K, P), axis(K, A), split(P, A, _, L).

    // p lies in the run labeled id, on the line at l.
    .decl run(key: Key, p: Position, l: Position, id: Ident)
    run(K, P, L, Id) :- _comps.label([K, L], P, Id).
}
```

Not: connectivity over a whole set, with no axis; a mover's reach from a standing position, which individuates no segment; a cast from designated marks, with the step count consumed; members packed into a frame by their lines; `DividerFrame` parts read by their count from an edge, where the dividers are the given structure and the ordinal is consumed. These exclusions turn on the configuration, not on the comp a site is built from: a site that individuates every maximal segment of its set is this operation whether it reaches that through `Components`, `Ray`, or `Slide`.

Match: a `Components` instance whose node key pairs a line position with the caller's own key, the line taken off the cell with `split` or `cell_split` — grep `\.node(\[` over `programs/solvers/`, then confirm a line-valued component in the key. A node set that is already axis-only (one line position per node, no cell within it) matches too, since the line key collapses. Two further forms carry no `Components` instance: a `Ray` self-marked on the node set, with `blocked` set to that set's complement, and a `Slide` whose segment ends are read off `rim_dir` and `rest`. A `DividerFrame` whose dividers are the node set's complement on the run axis, with `part_of` or `tile_of` consumed as identity alone, is a fourth.

Survey: 2026-09-08 00:45

Result: over the 540 solvers, ten sites hand-write the operation in four forms — line-keyed `Components` (the code form above), an axis-only node set whose line key collapses, `Ray` self-marked with `blocked` set to the node set's complement, and `Slide` with the segments read off `rim_dir`/`rest`. Every caller pairs a run with its extent or its ends (`Bbox`, `Tally`, `run_ends`, `run_reach`, `far_end`), and those compose from the id as lib stands. No site asks for a diagonal run, so `Axis` rather than `Axis4` is right, and the `l` column earns its place: 1ae2feb7 carries it through to the claim rule. The near-misses are `Components` and `Reach` over a whole set with no axis (5289ad53 `blocks`, 48634b99, 21897d95, 12eac192, 4364c1c4, 150deff5, 37d3e8b2, 1e5d6875, 142ca369, 3d588dc9, 3aa6fb7a, 45a5af55), casts from a designated mark with the step count consumed (06df4c85, 08573cc6, 50846271, 5168d44c), a mover's reach from a standing position (136b0064, 18286ef8, 332f06d7), grouping by line with no contiguity test (08ed6ac7), a degree test that individuates no segment (477d2879), transitive merging by span overlap (0a1d4ef5 `cls`, 2d0172a1), and a periodic phase from `divide_by_size` (3bdb4ada).

Spec question: how a run is identified, given that `Components` draws its id from the lowest-ord member cell and does not fold the key in, so two internal keys whose node sets overlap can share an id. Settled 2026-09-08: a run is `(key, l, id)`. Within one key the lines partition the cells, so `id` alone separates that key's runs; a caller reading both axes keys by axis, and there the two keys share cells, so the triple is what separates. `run` already carries all three columns, so the comp stands as written.

Callers:
- 5289ad53 — `runs`, in the `$Runs` case: a mark is a contiguous segment of a mark color within one line.
- 1ae2feb7 — `runs`: the maximal blocks of one color inside one line of the inked side; a run's length is the period it stamps.
- 4290ef0e — `run`: the arms a line cuts a ring into, on both axes at once.
- 746b3537 — `runs`: the maximal blocks of adjacent same-colored stripes across the sequence axis.
- 1190e5a7 — `bands`: the maximal blocks of adjacent non-divider lines on each axis.
- 0a1d4ef5 — `runs`, in the `$Runs` case: the maximal blocks of adjacent occupied lines per axis.
- 22a4bbc2 — `run_of` with `boundary`, in the `$Run` case: the maximal bands of same-colored rows along the stacking axis.
- 2b83f449 — `run` with `open_rim`: the maximal stretches of open cells along a corridor.
- 36a08778 — `run` feeding `span`: a block's maximal run along each axis.
- 2ccd9fef — `run` with `run_ends`, `run_cell`, `run_line`: the maximal segments of a frame's content inside each line.
- 33067df9 — `run` with `run_reach` and `span`: the maximal blocks of like-colored tiles along the run axis.
- 67c52801 — `slots`: the maximal bg segments of the marker row, each a slot.
- 18447a8d — `band_cell`: the maximal blocks of inked lines along the band axis, read as `DividerFrame` parts with the blank lines as dividers and the part position consumed as identity alone.
- 758abdf0 — `runs`: the maximal blocks of mark cells along the axis away from the wall; a run's length decides whether it grows or leaves.
- 42918530 — `box_of`: the boxes are the product of both axes' maximal runs of inked lines, read as `DividerFrame` parts with the blank lines as dividers and `tile_of` consumed as a key alone.
- 4f537728 — `blocks`, in the `$Block` case: the same blank-line dividers on both axes, tile positions compared with `same_line` as identity alone.
- 5dbc8537 — `panels`: the same blank-line dividers on both axes, `tile_of` consumed as the panel key alone.

Survey: 2026-09-09 22:35

Result: over the 380 solvers changed since the previous survey, no new caller and no reimplementation. The listed callers' sites are unchanged in form. Near-misses: 45a5af55 `core`, a seeded `Reach` over axis-only line positions that selects the one stripe touching the inner edge and individuates that segment only; 18447a8d `band_cell`, the maximal blocks of inked lines read as `DividerFrame` parts with the blank lines as dividers, the same structure 1190e5a7 `bands` reads with axis-only `Components`; whole-set `Components` named as bars or bands with no axis (673ef223, 48634b99, 53fb4810, 5623160b, 5af49b42, 64efde09, 1acc24af, 19bb5feb, 292dd178); grouping by line with no contiguity test (2601afb7, 41ace6b5, 4612dd53, 2685904e, 4be741c5); 195c6913 `strip`, swatches packed into an `OrderFrame` by their lines; 1d61978c `streak`, a diagonal degree test; casts from designated marks (5168d44c, 1190bc91, 292dd178 `flow`, 342ae2ed, 64efde09 `back`, 673ef223 `cast`, 36a08778 `wet`); seeded or whole-set `Reach` with no axis; every `Slide` site, a mover's rest; 5d588b4d `run_cell`, runs generated for the output from a square's diagonals.

Spec: no change. `Axis` over `Axis4` holds (no site individuates a diagonal segment), and the `(key, l, id)` identity stands. Ruling 2026-09-09 (67c52801 session): 18447a8d `band_cell` consumes its part positions as identity alone, so by the `Not:` line's own rule it is this operation through `DividerFrame`, and it goes under Callers; `DividerFrame` stays a peer only where the ordinal is consumed, which the `Not:` line now names.

Survey: 2026-09-10 03:32, over the solvers at or after the previous survey's time

Result: over the 334 solvers in scope, read by every `Components`/`Reach`/`Closed`/`DrawnRect` node rule, every `Ray`/`Between` self-marked cast, every `Slide` readout, every `DividerFrame` divider rule with its consumers, a parser pass over recursive `neighbor`/`jump`/`same_line` steps, and the vocabulary. The listed callers in scope are unchanged in form. New callers: 7039b2d7 `bands`, a `// family: 1190e5a7` sibling, counted with 1190e5a7; 42918530 `box_of`, 4f537728 `blocks`, 5dbc8537 `panels`, each a `DividerFrame` with blank-line dividers on both axes and the tile position consumed as identity alone, under the 18447a8d ruling; and the surfacing solver 758abdf0 `runs`. Near-misses all fall in named classes: whole-set connectivity with no axis (5623160b `run`, 48634b99, 673ef223, 53fb4810, 444801d8, 4acc7107, 54d9e175, 4e34c42c, 626c0bcc, 753ea09b, 13e47133, 239be575, 5961cc34, 4c416de3, 71e489b6, 1acc24af, 5ecac7f7 `shape`, 538b439f); seeded `Reach` (45a5af55 `core`, 182e5d0f, 0d87d2a6, 2f767503, 3dc255db, and the `outside` sites); casts from designated marks with the step count consumed (5ad8a7c0, 256b0a75, 3490cc26, 5545f144, 34cfa167, 50846271, 1478ab18, 08573cc6, 13e47133, 623ea044, 6d58a25d, 6ffe8f07, 759f3fd3, 1190bc91, 4c3d4a41, 50c07299); `Between` spans read as extents (22eb0ac0, 25c199f5, 1f876c06, 40853293, 55783887, 4290ef0e `side`); every `Slide` site; `DividerFrame` over given separator lines or with the ordinal consumed (18286ef8, 2e65ae53, 6350f1f4, and the separator-cut sites); grouping or adjacency with no segment (4612dd53, 477d2879, 4be741c5, 4aab4007, 4c7dc4dd, 52df9849); path-dependent walks (1e97544e `stripe_step`, 89565ca0, 5207a7b5, 1d61978c); runs generated for the output (5d588b4d, 58490d8a, 5833af48, 5ad4f10b).

Spec: no interface change; `Axis` over `Axis4` and the `(key, l, id)` identity stand. Four callers (42918530, 4f537728, 5dbc8537, the 1190e5a7 family) read the runs of both axes glued into a 2D tile, the row-band × column-band product of a blank-line tiling; `Runs<Key>` serves each axis under an axis key and the caller pairs the two ids, as 1190e5a7 does. The `Match:` line should name that 2D form so the next survey reads it directly. Those sites also show `DividerFrame` returns ordinals the callers read as identity only; the `Runs` id is the faithful type there.

Reimplementations: none.
