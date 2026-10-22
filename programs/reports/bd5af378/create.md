# bd5af378

## Departures
- The solver has no `$LByMinority` case, and the witness file has no `tiny-grid` witness: `$LByMinority` fails Subsumption. That case finds the L by the same edge test as the concept and only adds the condition that the field outnumbers the L. All corners that pass the edge test share one L color and one field color, so on every input and at every assignment of `shift` and `fill_color`, the case is either undefined or gives the concept's output. `witness` reported that no run shows it defined and differing. With that case gone, `tiny-grid` separated nothing. `witness --file work/task/bd5af378/witnesses.json` reports `$LByMinority` as a name with no case, on `thick-l` and `tiny-grid`, for this reason only.
- `Choice` is the l-thickness ADT itself (`OneLayer` / `MoveWholeL`): after `$LByMinority` left, the l-identification point had one branch.

## Judgments
- Keywords `move depth`: the L translates inward along the diagonal, and each cell's color depends on its distances to the two edges of the L's corner.
- const-join hint on `out` (`params.shift` with `params.fill_color`), kept with `@ignore`: the two values are independent parameters, and one relation over both would join unrelated values.
- The `deletions` finding on `diag_dir_elem(C)` in `corner_color` was acted on: `corner_dist` already enumerates the corner, so the atom was removed.
- Determine derives `fill_color` as the output color at the input L's corner cell, and `shift` as the nearer-edge distance of the output's L-colored cells. The plan listed proposers (`AnyOutNewColor`, `DivisorRatio`) that get these values from other facts, and `DivisorRatio` (a ratio of grid dimensions) has no relation to the step. So the determination reads each value from the fact the concept claims.
- The L parse (`corner_color`, `edge_defect`, `l_line`) is in `Parse<Key>` because the program and Determine both use it.
- Develop step 3, Not formed items: no branch was formed. The opposite-corner diagonal fails Fit at train0 and has no relational form on non-square grids. The "only the two L corners" reading gives the same output as the concept at `shift` 1, which is the only value of `shift` the generator gives, so it fails Equivalence. The swap reading is the concept's model. The `shift` derivation item has no proposer that fits (`derive` reports none).
- Develop step 4: `derive` reports no fitting derivation, and `store` reports no findings. The Analyze report gives no witness for `corner=stored`, `l_color=stored` or `field_color=stored` (each fails Fit), so no `@store` or `@derive` branch is held.
- `MoveWholeL` reads the L's thickness as the L-colored input cells that land on a cell when it moves `shift` cells toward the corner (`jump`). Its output on `thick-l` matches the Analyze file.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
