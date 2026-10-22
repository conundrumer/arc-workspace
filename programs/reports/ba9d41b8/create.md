# ba9d41b8

## Departures
- The solver has a `Punched` choice point with `$SizeThreshold` (an object is punched only when its box spans at least `min_extent` cells on each axis, stored as 5) and a `HoleFill` choice point with `$HoleColor` (holes take a stored `hole_color` 0 in place of `background`). Neither is in the Analyze report: Develop step 3 forms each interpretation under Not formed that states one model. Both fit every pair and have a relational form. `$HoleColor` meets the case conditions even though the Analyze report calls its parameter redundant. Under that branch, the hole color does not follow from `background`, so the model is not the concept's model with an extra parameter. The witnesses are `small-rect` (ordinary, concept) and `field-color` (variant, concept, `background` reassigned to 5).
- The Not formed items that were not formed are these. The derived `anchor` (the corner nearest a grid corner) is equivalent to the concept at a stored `anchor`, or it fixes task data in the program. The checkerboard counted from the inside's first cell is equivalent to the concept. Both fail Equivalence. The "period other than 2" reading is the concept case itself, because the program reads the period from `params.period` (literals are banned).
- `hole_color` has its own `@derive DominantColor: variant derived` branch, because `derive` reports that it fits. Its witness is train0 with 0 and 1 swapped. The generator would punch holes of the field color 1, which is that branch's output.
- `$GridFrame` reads `grid_anchor` (TR), `grid_hole_parity` (0) and `grid_tile` (anti-diagonal). These relations are separate from `anchor`, `hole_parity` and `tile`. The Analyze report separates only the anchor. These are Distinct parameters: take a task whose grid has odd extents and whose rectangles are odd squares at an odd distance sum from the grid corners. That task fits both cases and admits parity 0 for the concept and only 1 for `$GridFrame`. The tiles are distinct in the same way. In this task, `$GridFrame & $StoredTile` needs the anti-diagonal motif when it counts from TR.
- Witness `striped-tile`: the Analyze file's `assign` `{"tile": [[0,0],[0,1]]}` gives (row, col) pairs. The solver's `tile` holds Positions of the motif's 2x2 frame, so the `assign` is rewritten as `[[[0,1,0,1]], [[0,1,1,0]]]`, the same top row. With it, `$ObjectCorner & $StoredTile` gives the Analyze file's `$StoredTile` grid. `witness --file work/task/ba9d41b8/witnesses.json` still prints a mismatch for `$StoredTile` on that witness, because it reads the Analyze file's `assign` shape. The same witness also reassigns `grid_tile` to the top row, so that `$GridFrame & $StoredTile` is a witnessed case (otherwise it equals `$GridFrame & $Checker` at the stored values). It has a `@reassigned grid_tile` line.
- Added witness `zero-rect`, which separates `hole_color=DominantColor` from `background=DominantColor` (the audit reported this pair unseparated). It is a field of 1 with a rectangle of 2 and a rectangle of 0. Judgment: `variant`, because the field is a color permutation of a train input. The generator would punch both rectangles with holes of 1, so the verdict is the output of `background=DominantColor`.

## Judgments
- Parity has no lib relation. The solver writes it as `corner_dist` from the box corner (through `crop`), folded by `stride(T, N, 0, _, K)` with `period` 2 from Params, after the precedent of 2072aba6. `period` is a stored parameter only because literals are banned. The concept fixes it at 2.
- `$StoredTile` reads the motif as a `GRID_MASK_2x2` of hole Positions. The motif is laid from the counting corner by `diag_dist` on both the cell and the motif cell, and the period on each axis comes from the motif's own frame (`axis_dims`), so the encoding is equivariant.
- The object readings use four component instances: `Parse.comps` (one color, 4-adjacent, shared with Determine), plus `same8`, `any4` and `any8`. The components step is not keyed, and the one-color split needs a color key. These differences mean no instance can be shared across cases. The concept's boxes come from `parse.box`, and the other readings' boxes come from `obox`, so Determine shares the concept's derivation.
- Hint `common-subexpr` on Determine's `grid_hole_parity`: kept with `@ignore`. The shared atoms count in the grid's frame there and in each object's box in `hole_parity`.
- Deletions: `!params.background(Col)` in Parse, the `any8` clauses, `small` and `!small` are not exercised by the pairs or by the witnessed cases. They encode claims of the concept or of a case, so they stay. `parse.object([E, Id], P)` in `hole_parity` ties the hole to its object, and stays. `ex_out(E, _, _)` scopes `min_extent` to train examples, as the Test inputs rule requires, and stays.
- `min_extent` is determined as the least box extent over the train inputs' objects (5). The sweep reports 0–4 also fit. `min_extent` is not an open parameter of the concept, because the concept case does not read it. Values 0–3 make `$SizeThreshold` agree with the concept on every input of the scene, so 5 is stored alone.
- `background` and `hole_color` are determined from the color the train outputs repaint, which is a fact other than DominantColor's. `period` is determined as the least step from a hole to the next hole on its row or column (Ray, Extremes). `hole_parity` and `grid_hole_parity` are determined from the holes' distance sums. `anchor`, `grid_anchor`, `tile` and `grid_tile` are left to fit enumeration: the plan reports 1 of 16 joint assignments reproduce every train pair.
- Keywords: `objects border wallpaper parity`.

## Open
- The plan still lists `anchor` and `grid_anchor` under "write a determination relation" with `domain enumerable(4), pairs-exact`. No proposer derives them from another fact, so the pass leaves them to fit enumeration. A reviewer's reading of the plan line would settle whether a determination relation is required.
- The sweep lists `tile` and `grid_tile` values in frames other than 2x2 as fits. Those values are outside Θ for a 2x2 motif. A runner fix (ticket 10-559) or a frame-free motif encoding would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-559_task_ba9d41b8_create.md
- 10-560_task_ba9d41b8_create.md
