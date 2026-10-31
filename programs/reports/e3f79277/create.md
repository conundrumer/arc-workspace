# e3f79277

## Departures
- The `background=DominantColor` branch is a `@derive DominantColor: variant derived` line on `background`, with `@relaxed corner-angle`. It has no constructor: [Write](#write) leaves out a branch that a built-in derivation gives.
- The Analyze witness `background=DominantColor` (a field of 3) is removed from the witness file. `derive` recorded its own witness for the same branch (train0 with 7 and 0 swapped), under the id `background=DominantColor`, and the Analyze witness duplicated it.
- The concept constructors take names of their own: `$StoredSize` at the `out_size` point and `$EqualLegs` at the `leg-length` point. `record --all` wrote these names into the groups that `witnesses.json` gives as `concept`.

## Judgments
- The output legs are found without arithmetic. A cell on a corner edge is a leg cell when `stride(dist, leg_scale, 0, I, _)` puts it in a run I with I less than the input leg length k. Then the leg covers distances 0 to leg_scale·k − 1, and it is correct for an output extent of any parity.
- The hypotenuse is the set of cells whose `corner_dist` to the angle's corner equals the `corner_dist` of a leg's far end. A far end is a leg cell whose next cell along the edge is off the leg.
- The leg length k is a `Tally` of the angle cells on each edge of the corner. `$EqualLegs` reads it through `Unanimous`, so the concept is undefined where the legs differ. `$LongerLeg` and `$ShorterLeg` read it through `Extremes`.
- `$SizeFromInput` has a relational form: the output extent on each axis is the `Tally` of the input's lines together with the lines of a `size_gap`-extent `AxisFrame`, so the sum is a count of members and needs no arithmetic.
- The cases are all six combinations of the two points. Five are witnessed: the concept, `$SizeFromInput`, `$LongerLeg`, `$ShorterLeg` and `background=DominantColor`. The combinations of `$SizeFromInput` with `$LongerLeg` or `$ShorterLeg` give no output that a case with fewer non-concept branches does not give. Both points are in the same `out` column, so `witness` reported no unseparated pair.
- Determination: the plan listed `leg_scale` (TileCount narrowed to 3 values), so `Determine` derives it with `tile_size(M, N, 0, K)` from the input and output leg tallies, and keeps a value only when every example with an output shows it. The plan also listed `background`, `out_size` and `size_gap`. Their proposers (DominantColor, ConstOutDim, DimDiff) read the same facts that the concept reads (the field color, the output side, the output side less the input side), so no determination relation is written for them.
- `Parse<Key>` holds the angle, its corner and the leg tallies. The program and `Determine` share it. `Determine` also reads the output triangle as an angle through a second `Parse<Example>` instance on `ex_out`.
- Deletions: removed the `impl_choice` atoms in `leg` and `out` and the `lines.domain` rule, and then removed `impl_choice` and its enumerators, because no clause reads them and the cases are every combination of the fields. Kept `leg_length(_, L)` in the background clause of `out`, because it makes the case undefined where no leg length exists. Kept `defect`, the universal check of the determination, which the pairs do not exercise because they agree on a single value.
- `store` printed no line to add. Its derived values (`canvas.cell`, `canvas.extent`, `lines.item`, `lines.tally`) have no witness under a D4 image or color swap of a train input.
- Keywords: `scale` (the legs correspond across the size change), `count` (the leg length sets the output leg extent), `grow` (`$SizeFromInput`: the output frame extends the input frame).

## Unsettled
- `deletions` ran once, before the last edits that applied its findings. The pairs run and `witness` passed after those edits, and no later `deletions` run confirms that nothing else is redundant.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
