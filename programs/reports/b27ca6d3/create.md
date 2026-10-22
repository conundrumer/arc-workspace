# b27ca6d3

## Departures
- `$LargestSize` is defined on an input with no marks, where it frames nothing and the output is the input. The Analyze report gives it as undefined there. The keep rule reads no size, so with no group the case has a whole output. No witness has such an input.
- Witness file, `bar-and-l`: the `assign` of `footprint` is three Position facts of a 1×3 frame. The Analyze file gives the grid `[[2, 2, 2]]`, which the `GRID_MASK` layout cannot read, because a member takes 1. The Analyze file erred here. The outputs are the same as the Analyze file's.
- Stored `footprint` is the vertical domino (`GRID_MASK_2x1`). The model reads the footprint only up to D4, so its pose has no effect on any output. The Determine relation takes the shape of one framed group per D4 class (the `Canon` representative), and on these pairs that shape is train0's vertical pair.
- The choice point `frame-target` is a field of the top-level `Choice` record. The Analyze report nests it under the concept branch of `grouping`. `$Join8` fails Fit, so `grouping` has no other branch in the solver, and `frame-target` stands beside the other points.

## Judgments
- `@derive TileCount` on `pair_size` (`variant concept`, `@relaxed marks`): `derive` reports that it fits. The Analyze report leaves it out. On an input it gives every tile count in 2..8 that fits a side of the grid, so the `$SizeEquals` case frames every group of such a size. Its witness `pair_size=TileCount` is the `three-bar` input, which breaks `marks`, and the generator would frame the pair alone.
- Witness `five-bar` (built for the unseparated pair `$SizeAtLeast & pair_size=stored` and `$SizeEquals & pair_size=TileCount`): a pair and a five-cell bar on a 7×7 grid. No count of 5 tiles fits a side of 7 at gaps 0..3, so TileCount leaves out 5. Plausibility `variant`, because the five-cell bar breaks `marks`. Verdict `concept`, because the generator frames groups of `pair_size` cells.
- `@derive DominantColor` on `background` and `@derive RarestColor` on `mark`: `foreign concept`, as the Analyze report gives.
- `store` lists `largest.high` as stored already: on every input it equals `pair_size`, so its stored branch is the `$SizeEquals` case and adds no line.
- Not formed, "a frame color chosen by the bar's axis": a per-axis frame color takes one value for both axes in every task the generator makes, color permutations included. At those values its model agrees with the concept case, so it fails Equivalence.
- Not formed, "a frame wider than one cell, or a stamped footprint": as the Analyze report gives, the width has no value but 1, so a width parameter's model is the concept case's model and fails Equivalence.
- Not formed, `pair_size` by a proposer and the other color proposers: TileCount fits and is held. The other proposers give no value or fail Fit, and `derive` lists none of them.
- `deletions`: `!inside(Q, B)` in the `$BoxRing` clause stays, because it keeps the box's own cells out of the ring, and the `l-tromino` notch cell depends on it. `in(Q, _)` stays, because without it `$BoxRing & $FrameOverMarks` writes cells off the grid where a pair lies on the edge, as in train1. The bound `dir8_elem(D)` enumerators stay.
- `Parse` holds the group boxes and the shapes in their own boxes, because `Determine` reads the same derivation.

## Open
- none

## Lib
- The cells that touch a cell set at a side or a corner (the `$Halo` clause): `parse.group([$U(), Id], P), dir8_elem(D), neighbor(P, D, Q), in(Q, _)`. The grep `dir8_elem(D), neighbor(` finds 43 solvers, among them the approved 15113be4, 1b8318e3, 42a50994, 928ad970, 9b2a60aa, ce22a75a, dc1df850 and d9fac9be. The form is two lib atoms, so no comp is proposed.
- A shape compared to a stored shape up to D4: crop to the group's box, `apply(D, P, P_turned)` over `d4_elem(D)`, then `KeyedSetCompare.equals`. The approved 898e7135 has the same form for its holes and pieces. That form uses lib relations only, so no comp is proposed.

## Fixes elsewhere
- none

## Tickets filed
- 10-286_task_b27ca6d3_create.md
- 10-287_task_b27ca6d3_create.md
