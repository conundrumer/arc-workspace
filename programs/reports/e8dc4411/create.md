# e8dc4411

## Departures
- The cases `$MarkerInCopyStep`, `$MirroredCopies`, `$RotatedCopies`, `$MarkerInCopyStep & $MirroredCopies`, `$MarkerInCopyStep & $RotatedCopies`, `$NoOverlapStep & $MirroredCopies` and `$NoOverlapStep & $RotatedCopies` are left out of `impl_choice`. Each of them takes `$PastTipDirection`, and each fails Subsumption against the same base with `$AdjacentCellDirection`: where the past-tip direction is defined, the marker's other diagonal neighbors lie on its own anti-diagonal line or behind it, so the marker is diagonally next to exactly one template cell, and the adjacent-cell direction gives the same direction. Thus no input shows the past-tip case defined and different. The `witness` run reported this for the pairs it witnessed. Each of those branches now stands as its case with `$AdjacentCellDirection`. Before the exclusion, the run against `witnesses.json` showed the single-branch models of `$MarkerInCopyStep`, `$MirroredCopies` and `$RotatedCopies` giving the grids `witnesses.json` gives them. After it, `witness --file programs/reports/e8dc4411/witnesses.json` reports these three names as no case of the solver.
- The header's `@rule step` leaves out the concept file's sentence "the marker is a cell of the first copy": that sentence is false in general. `analyze.md` (bar-template) shows the concept leaving the marker apart from the copies.
- The concept's step is computed from the template's front line, not from the marker. The step is the K at which the template's back cell, translated K diagonal cells, lands on the line one diagonal step past the front line. This is the concept file's rule `step`. Where the template spans an odd number of lines, no K exists, and the case is undefined, as `analyze.md` states.

## Judgments
- `half_turn` was first a `Params` fact (`D4_HT`). The sweep showed that every D4 element fits the pairs, because every template is D4-symmetric. The half turn is not task data: it defines `$RotatedCopies`. It is now derived in the program as a quarter turn composed with itself (`rotation(_, R), d4_compose(R, R, H)`). This leaves no literal and no parameter.
- `shape_color` determination: the color that every example input holds. This is a fact of the inputs alone, and the plan reports it as determined.
- The repeated copies use the precedent of 045e512c: a `Ray` from each template cell, and `stride(J, K, 0, _, 0)` for a whole number of steps. The step lengths are enumerated from `sub_extent`. For the alternating forms (`$MirroredCopies`, `$RotatedCopies`), a second `Ray` casts from the first odd copy, and `stride(J, K, K, _, 0)` keeps every second step.
- The `$MirroredCopies` first copy reflects each template cell across the line one cell past the front. It moves the cell along its own diagonal by the count of grid diagonal lines from the front line to the cell's line (`Tally`). This avoids arithmetic on corner distances.
- The `deletions` items that are kept (`stuck`, `clash`, `defined`, `lone.value`, `short_of`, the diagonal-neighbor atoms, the `first_odd` gate on the even copies, `rotation`): each states a claim or an undefinedness condition that the pairs do not exercise. The removed atoms were gates that `direction` already implies (`march.dir`, `odd_march.dir`, `front`, `back`, `tbox.cell`). The single-consumer `back` was inlined into the `$SpanStep` clause.
- The run-output rule was broken once: in Develop, one pairs run was piped to `grep` to drop a uv warning line. That run passed. Every later run was read whole.

## Unsettled
- The `$SpanStep` step is found among the lengths `sub_extent` enumerates (below a grid extent). A template whose step reaches the larger grid extent would leave the case undefined. That needs a marker past a template that spans corner to corner, which puts the marker off the grid. A witness of such a grid would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
