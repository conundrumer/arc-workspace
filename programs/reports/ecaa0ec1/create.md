# ecaa0ec1

## Departures
- The witness file has no `background=DominantColor` witness, and its groups name that branch `bg=DominantColor`. The `derive` run recorded its own witness `bg=DominantColor`, which is train0 with 0 and 2 swapped. That witness duplicates the Analyze witness for the same branch, so the Analyze witness was removed, as Witness requires. The background parameter is `bg` in Params, so the branch's name is `bg=DominantColor`.
- The witness file holds one witness that Analyze does not give: `stray-marker`. The pairs and the Analyze witnesses showed `$TargetByDiagonal` and `$TargetBySideMarks` defined and differing from `$TargetByQuadrant` on no input, and `witness` reported this. On `stray-marker`, a fourth marker stands in the top-right quadrant. The concept, `$TargetByDiagonal` and `$TargetBySideMarks` turn the tile and wipe that marker. `$TargetByQuadrant` and `$PointerByQuadrant` are undefined.
- Concept constructors have names of my own: `ThreeMarks` (marked-corner), `DiagonalPointer` (pointer) and `TurnWithTile` (pointer-placement).

## Judgments
- `stray-marker` is `borderline concept`, with `@relaxed no-other-marker`. The generator puts no fourth marker in any pair. If it did, the concept output, with every non-tile, non-pointer cell wiped, is what it would pair with that input.
- `@derive DominantColor` on `bg` is `variant derived`, with `@relaxed tile`. Its witness swaps 0 and 2. That is a color permutation, and at bg 0 the field of 2 would count as tile.
- `@store` on `tile_color` is `variant concept`, with `@relaxed tile`, as Analyze gives for `tile_color=stored`. The `store` run printed "make it a parameter" and gave no `add:` line. The `@store: <plausibility> <verdict>` form was accepted, and the audit's store check passes.
- `mark_gap=TileCount` and `mark_gap=TileDim` fit the pairs. Both are `@ignore: derive` for Relational form: no tiling divides the grid, so a tile count or tile size of the grid's extent counts nothing the task has. The witness `mark_gap=TileCount` that `derive` wrote was removed with them.
- Determine reads each parameter from the evidence, with one value that every example agrees on (`Unanimous`):
  - `bg` is the commonest input color.
  - `marker` is the input color whose cells become `bg` in the output.
  - `pointer_gap` is the diagonal steps from an output tile corner to the output marker.
  - `mark_gap` is the steps out from an input tile corner at which a marker stands on the diagonal and in line with both sides.
- The plan's proposers `ChangedColor` (marker) and `DivisorRatio` (pointer_gap) are not used. The determinations above derive the same values from the concept's own structure.
- `deletions` reported atoms that change no pair output. They were judged as follows:
  - The `$ThreeMarks` and `$TargetBySideMarks` mark atoms, and the Determine `mark_value` atoms, stay. The pairs always have all three marks, so these atoms state the claim and are not redundant.
  - `ambiguous`, `crowded` and the joint `$TargetByQuadrant & $PointerByQuadrant` candidate clause stay. They give the undefinedness and the joint definition that Analyze gives, and no witnessed case reads them on the pairs.
  - The column `turned.r` and the `tile_turn` atoms in the turned-pointer clauses stay. They bind each case to its own rotation.
  - `tile_turn(Ch, _)` in the `$PointerSnapsToDiagonal` clause was removed. `target` and `pointer` imply it. `deletions` ran before this one-atom edit and was not rerun, as Simplify allows one run. The last pairs run comes after the edit and passes.
- Develop step 3 adds no branch. Each item under Not formed either has no relational form (the centroid corner) or fails Fit (`bg=SharedColor`, `bg=RarestColor`, fixed turn, 8-connected tile, pointer onto the diagonal mark, color swap).
- `$Reflect`, `$KeepMarks`, `marker=RarestColor` and `marker=SharedColor` fail Fit at train0, as Analyze gives. They have no constructor. `derive` lists no marker derivation.
- No rule is approximated.
- Final state: every pair passes with 8 witnessed cases, lint is ok, the determination is ok for `bg`, `mark_gap`, `marker` and `pointer_gap`, and every audit check is ok.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
