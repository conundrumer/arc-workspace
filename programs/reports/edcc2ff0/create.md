# edcc2ff0

## Departures
- The panel/field split counts a cell as field when its row or its column holds no `panel_color` cell. The concept counts it as field when its row holds none: the program can't fix rows, because a rotated variant puts the panel on another side. The two splits agree on every input with a full-width panel, which holds for every input the generator produces, so `same_line` runs over both axes and no axis parameter is stored.
- Added branch `$FieldBgGridCommonest` (the field background is the commonest color of the whole grid), from the second Not formed item of `analyze.md`, as Develop step 3 requires. It fits every pair. Witness `cluttered-field`: unlisted objects fill half the field, so 3 (66 cells) is outnumbered by the panel's 0 (67 cells). Judged `borderline` (the generator's fields hold far fewer object cells) with verdict `concept`. It breaks no stated scene claim, so it has no `@relaxed` line.
- Added `@store` branches `field`, `line_has_panel`, `ray.cell` and `ray.mark`, as Develop step 4 requires (`store` printed a line for each). Each takes `variant $BarDirFromEdge` with `@relaxed legend-panel`: the witness `store` built is train0 turned a quarter turn, whose generator output is the rotated train0 output, and that output is what `$BarDirFromEdge` gives.
- `ray.ray=stored` dropped under Equivalence (`// @ignore ray: store`). On a 20×10 grid it gives the same casts as `ray.mark=stored`, because a marker at col 0 only ever casts toward DIR_R. On a grid of any other size no stored cell matches a cell of the grid, so both draw no bar. The two take equal counts of non-concept branches, so `ray.ray=stored` is the one that leaves. Its witness was removed from the witness file.
- `$FieldBgFromBoundaryRow & line_has_panel=stored` dropped under Subsumption (`// @ignore: store $FieldBgFromBoundaryRow`). On 20×10 grids it gives the same field as `field=stored`. On any other grid every cell is field, no cell borders a panel, and the case is undefined.
- Built witnesses `deeper-panel` (a 9-row panel, which separates `field=stored` from `field=derived` under `$BarDirFromEdge`), `wide-grid-long-bar` (a 15-wide grid, which separates the stored ray values from the derived ones) and `small-grid-edge-cells` (a 5×3 grid, which separates `line_has_panel=stored` from `field=stored` under `$BarDirFromEdge`). Plausibility: `deeper-panel` is `borderline`, and the other two are `foreign`. Verdict for all three: `concept`. None of the three has a `@witness` line, because each separates `@store` cases.
- The run against `witnesses.json` printed no difference.

## Judgments
- The Not formed item on a panel/field split by the region of `panel_color` cells states no single model: the markers are not `panel_color`, and the item does not say how they join the region. So no branch was formed from it. The other Not formed items fail Fit, or they name no proposer.
- Case-marker hints: shared clauses were moved above every marker. `Ray` was keyed by `BarDir`, so a stored-direction case no longer reads the edge-derived casts. Lint is clean of those hints.
- Deletions: the `objects.domain` clause and the `impl_choice` atom in `bar` were removed. A color with no object gets no tally, so its marker draws no bar and the panel clause erases it, and the tally key grounds every `Choice` field. The other atoms that `deletions` flags stay. The pairs never instantiate their structure: a marker on a corner or on another edge, the boundary-row background, or a component of mixed colors.
- `@derive`: `derive` reports no built-in derivation that fits.
- Keywords: `objects markers count select`.

## Unsettled
- `panel_corner` (branch `$PanelColorFromCorner`): the sweep and the plan show that DIAG_TR fits the pairs as well as the stored DIAG_TL. This is an open parameter. Storing both values as `@open` needs an `OpenValue` column on `out`, threaded through every relation keyed by `PanelColor`. That was not done. The determination relation keeps the corners whose cell holds the panel's color and that lie on the edge the markers lie on, so it gives the stored DIAG_TL alone.
- The audit's relabelings check fails: "`ray.mark` is not one value on every input at the case values the cases that take its `@store` branch hold; it differs on train 1". The cause was not found. Keying `ray.mark` by more of the `Choice`, or reading how relabeling treats the stored marker cells, would settle it.
- The final pairs run takes 26 s with 22 witnessed cases. `audit` and `deletions` were each run on the final design, before the last two small edits.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
