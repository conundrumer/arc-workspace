# e45ef808

## Departures
- Witness id `$GroundSideFromBorder` is `ground-side-from-border` in the solver and the witness file: lint rejects a `@witness` id that is not a slug.
- The `$FarthestGround` height counts a column's cells from the ground edge through its farthest ground cell, so a column with no ground counts 0 and ranks lowest. This matches the outputs that `witnesses.json` gives on `ground-side-from-border`, where columns with no ground tie for the valley.
- `ground-recolored`, `$ValleyTieSide` and `$ValleyTieAll`: the solver is undefined, and `witnesses.json` gives grids. Every column ties at height 0, so the peak line and the valley line fall on the same column, col 11 or every column. The solver gives such a cell two colors, so no total grid comes out. `witnesses.json` paints the valley color over the peak color, and no claim of the concept or of the branch states that order.
- Each case that takes `$UniqueValley` together with another non-concept branch leaves under Subsumption. Wherever `$UniqueValley` is defined the valley is unique, and then every valley-tie branch gives the same output, so the same case with `$ValleyTieSide` subsumes it. `impl_choice` gives `$UniqueValley` to the concept case alone. Branch models such as `$CastFromBorder` and `$GroundCount` are therefore no case of the solver, and each is stood for by the case that takes that branch together with a valley-tie branch. `witness --file programs/reports/e45ef808/witnesses.json` lists those names as models with no case.
- `@store` points `border_edge`, `off_border`, `layout_sky.item` and `layout_ground.item` carry `@ignore: store`: a stored value of each fixes the ground side, sky color or ground color to the value that `$StoredSide`, `$StoredSky` or `$StoredGround` stores, so it fails Equivalence.

## Judgments
- `@derive RarestColor` on `border_color` (variant, verdict derived, relaxes `border-row`): the `derive` witness is train0 with the border recolored 2. A recolored border is a routine variant, and there the derived border finds the top row and draws the train0 lines.
- Witness `border-stone`, built so that `$GroundSideFromBorder` with the stored border color meets Subsumption against `border_color=RarestColor`: train0 input with one 2 cell at (11,0). RarestColor takes 2 as the border and is undefined. The stored 0 border draws both lines. It breaks `sky-and-ground`, so it is not `ordinary`. The solver has no `@witness` line for it, as Params gives for a further witness of a `@derive` branch.
- `$TieFarFromValley` and `$ValleyTieFarFromPeak` resolve their ties in two layers, `peak_first`/`valley_first` and then the `Ray` distance from the other line's column. One relation that reads the other's result would make a cycle through negation. With both branches and both ties, neither layer gives a column, and the case is undefined, as `analyze.md` states.
- The concept is undefined where the final peak or (outside `$ValleyTieAll`) the final valley holds more than one column. This covers `tie_side` on the ground axis under `$GroundSideFromBorder`, as `analyze.md` states.
- Determination: `sky_color` is the input color of the cells the output repaints. `border_color` is the color of the one edge line that holds one color found nowhere else. `ground_side` is the edge opposite that line. `ground_color`, `peak_color`, `valley_color` and `tie_side` stay with the fit enumeration: the plan reports them covered, and 1 of 4 joint assignments reproduces every train pair.
- Common-subexpression hint on `edge_mixed`: merged the two clauses into one disjunction.
- `deletions`: the 44 deletions that change nothing remove tie handling, undefinedness checks and `$CastFromBorder`/far-from tie structure that the pairs never instantiate, and the witnesses exercise them. The `impl_choice(Ch)` atom in `layout_ground.item` is redundant with `ground_side(D, Ch)`. It stays, because `deletions` runs after the last edit.
- Keywords `lines rank markers`: per-column heights (`lines`), extremum columns (`rank`), and the border row that fixes the ground side (`markers`).
- Not formed in `analyze.md`: no item states a model to form.

## Unsettled
- `store` did not check `column`, `drop.cell`, `ground_cell` or `sky_cell` (over 20000 rows on an input): a store survey with a higher row cap would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
