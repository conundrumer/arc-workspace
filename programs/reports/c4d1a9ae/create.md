# c4d1a9ae

## Departures
- `$PanelCountStored` is not in the solver, and the witness file lists no group under it: it fails Subsumption. At each value of `panel_count` in Θ, which is two or more panels, the branch is defined only where the input has that many panels, and there it gives the concept's output. A value of 1 would make it defined where the concept is not, but a one-panel input has no next panel, so no task of this generator gives that value. The `@derive TileCount` and `@derive TileDim` branches on `panel_count` fit and were held, then left with it.
- Choice point `wrap` with branch `$WrapTwoBack` is added from the Not formed item "Another wrap at four or more panels". The item's example states one model: the last panel takes the color of the panel two before it. That model fits every pair, and its claim has a relational form (the predecessor of the predecessor). Witness `four-panels` separates it from the concept (cols 9–10 fill with 6 in place of 2), with verdict `concept` at `variant`.
- Witness `shared-color` is added (train0 with the third panel's ink recolored 2). Without it, no run shows `$Runs & $WrapTwoBack` defined and differing from `$ColorSpan & $WrapTwoBack`. On this witness `$Runs` fills the panels and `$ColorSpan` is undefined, because color 2's span overlaps the span of 6.
- Under `$AxisFromSeparators`, the Analyze file's "source-dir stores one direction per axis, R on H and an open value on V" is encoded as two relations: the shared `source_dir(DIR_R)`, and an `@open` relation `cross_source_dir` (T, B) that is read only where the derived panel axis is the other axis. On inputs where the panels run along the axis of `source_dir`, the facts hold `nil`, so the case gives one grid there. On `row-separators` it gives two grids, B then T, as the Analyze file gives.
- The concept branches are named `Runs`, `Commonest`, `SourceAxis` and `WrapFirst`. The Analyze file names them `concept`.

## Judgments
- The hint common-subexpr on `fill` and `ink` was resolved by the relation `panel_cell`, which states that a cell lies in a panel.
- The hint head-repeat on `site` was resolved by dropping the repeated `Site` column. The program rebuilds `Site` from the case and the direction.
- The hint head-repeat on `fill_dir` is kept with `@ignore`. The `OpenValue` column records the direction that the fact is read at.
- The two "case section" hints were resolved. The `sep_axis` clauses now stand under `$BgSeparatorColor & $SourceAxis` and `$BgSeparatorColor & $AxisFromSeparators`. The `$ColorSpan` panel clause now states `$ColorSpan` in its key.
- "Cut" is read as follows: a full line of one color cuts the grid when a line that holds another color stands on each side of it. `$BgSeparatorColor` and `$AxisFromSeparators` both use that reading. With both branches, the separator color is read from cutting lines across either axis.
- The concept's tie case (more than one commonest color) is made undefined by a `Unanimous` over the `Mode`. This follows the Analyze file's statement that the concept is undefined at a tie.
- `source_dir` has no determination relation. The determination plan covers it by "domain enumerable, pairs-exact", which keeps the directions at which the model fits the pairs, and that is the fact the concept reads it from. There is no Determine comp, because no other parameter needs determination clauses.
- The sweep admits L and R for `cross_source_dir`. Those values were not stored. That relation is read only on the V axis, where L and R give no direction, so no reader of the concept takes them.
- `shared-color`: plausibility `borderline`, because two panels sharing a color breaks `one-color-panel`. Verdict `concept`, because the generator would fill by position whatever the colors are.
- Keywords: `decompose` (separator lines cut the panels), `rank` (the panel order gives the fill color), `color-class` and `bbox` (`$ColorSpan` takes each color as a panel over its span).
- The other Not formed items are not formed. Ordering by color value or count, the last panel taking its own neighbor's color, and separators that fill all fail Fit. Panels as connected objects is `$ColorBbox`, which fails Fit. No proposer gives a direction for a derived `source-dir`.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-700_task_c4d1a9ae_create.md
