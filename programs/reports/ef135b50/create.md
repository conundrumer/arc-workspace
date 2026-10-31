# ef135b50

## Departures
- `background` is under the `$PerLineRun` marker in Params, not shared: the concept case never reads it. The concept's strip runs between two pieces, and its blocked-pair test reads `object_color`, so only `$PerLineRun` (background runs between object cells) reads `background`.
- `$PerLineRun & $AllLines` is not in `impl_choice`: `analyze.md` gives that it fails Fit at train2 row 9, cols 4-8.
- `$NearestNeighbor` and `$BothAxes` have no constructor: `analyze.md` gives each a Fit failure and no witness.

## Judgments
- Concept branch names of my own: `PiecePair` (gap-unit), `SideJoin` (piece-adjacency), `BoxStrip` (strip-extent), `AllLines` (border-lines). The `analyze.md` names of non-concept branches are the constructor names, so the witness file needed no renaming beyond what `record --all` wrote.
- The strip is stated through `Ray<Region>`: a cell is past a region toward d when a ray from the region toward d reaches it and no ray toward the opposite direction does. A pair's strip is the cells past each piece toward the other. With box cells as the region, this gives `BoxStrip`. With piece cells, it gives `$CellwiseStrip` (the cells past the near piece's last cell on a line). The lines the two pieces share follow from the rays, so no line is compared directly.
- Witnessed cases: concept, `$DiagonalJoin`, `$CellwiseStrip`, `$BorderLinesUnbridged`, and `$PerLineRun & $BorderLinesUnbridged`. `witness` reported no unseparated pair and no undifferentiated case.
- `derive`: no built-in derivation fits. `store`: no line to add (`border_line` has no witness under D4 or color swap, and the other values vary per key).
- Deletions that change nothing on the pairs, kept: `blocked.x`, `.y`, `.d` (the rule blocks one pair, not every pair of a piece); `params.bridge_axis`/`perp` in `border_line` (the branch suppresses only the border lines along the bridge axis); `impl_choice(Ch)` in the bridge-color `out` clause (it keeps the non-case `$PerLineRun & $AllLines` out of `out`). In Simplify, the axis filter in `front` was removed, because `cast.dir` already restricts the casts to the bridge axis, and the `impl_choice` atoms in the two `paint` clauses moved into `out`.
- Determination: `background` (the color a train output recolors) and `bridge_color` (the color an output holds that its input lacks) are read from the evidence. `object_color` (UnchangedColor) and `bridge_axis` had determination relations that kept values by a test that reads inputs and outputs together. The lint hint "determine prediction" fired on both. That is outside the determination's allowed forms, so I removed both relations. The sweep shows each of them unique on the train pairs (2, AXIS_H) by fit.

## Unsettled
- `object_color` and `bridge_axis` have no determination relation. The sweep fixes them by fit alone. A clause that reads `object_color` from the evidence, or keeps it by a fact of the inputs alone or of the outputs alone, would settle it. `determination-plan` was at its cap of 3 runs when I removed those relations.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
