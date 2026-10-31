# f35d900a

## Departures
- `$PartnerColor` is not in the solver, and its name is removed from the groups of the witness file. Reason: it fails Subsumption. It is defined only where a marker's row partner and column partner share a color. There, the nearest marker is one of those two partners, so `$NearestMarkerColor` gives the same grid. `row-colored` shows that `$NearestMarkerColor` is defined where `$PartnerColor` is not, so the two models are not equivalent. With `--file programs/reports/f35d900a/witnesses.json`, the only differences are the four "`$PartnerColor` denotes no case" lines.
- `$UnclippedArm` is a field of the `Choice` record, and `impl_choice` leaves out its combination with `$FullReach`. Reason: the pairs run showed that combination failing Fit at train1, train2 and test0, as `analyze.md` says.
- The witness file has two witnesses that `witnesses.json` does not have:
    - `reach_cap=SepThickness`: an 11×17 grid with markers at (1,1), (1,9), (6,1), (6,9). The only separator tiling it admits has gaps of 1, so the derived cap is 1. Each end of the long sides then dots one cell, where the concept and the stored cap of 2 dot two. I judge it `ordinary`, verdict `concept`: it breaks no scene claim, and nothing in the task caps dots at a separator thickness.
    - `long-side-field`: the `long-side` input on a field of 7. It witnesses the case `$CappedReach & background=DominantColor`. I judge it `variant`, verdict `background=DominantColor`, and it breaks `four-corner-markers`. It has no `@witness` line, because the stored-background cases are all undefined on it, so it does not separate `$CappedReach` from the concept.
- `reach_cap` has new `@ignore: derive` lines. `derive` found 7 derivations that fit, and `analyze.md` says under Not formed that none exists:
    - ConstInDim, TileCount, TileDim: these fail Equivalence. Each one gives a full grid dimension among its values, so no end reaches the cap.
    - Period: this fails Equivalence. The least period is longer than the span of the markers.
    - SepTileCount, SepTileDim: these fail Subsumption. A search of grids up to 18×18 found no input where the derived cap is less than the dots an end sends.
    - SepThickness: this one stays as a `@derive` branch. Its `$UnclippedArm` cases fail Fit at train1, train2 and test0.

## Judgments
- Parity has no arithmetic. A `Ray` cast from the first gap cell next to each ring gives the distance t, and `stride(t, w, g, n, _)` with `dot_spacing(1, 1)` keeps the cells that start a dot. n counts the dots before the cell, and `$CappedReach` compares n against `reach_cap`. The clip at the middle is `t1 <= t2`, which compares the two distances from the two ends. That comparison is a comparison of distances, not arithmetic.
- `dot_spacing(w, g)` is a new parameter. The literal ban requires one for the dot length and the dot gap. The sweep found only (1, 1) among the values it swept.
- `$NearestMarkerColor` picks the nearest marker among the markers in line with it. Those markers come from `ArgExtremes` over the distances that `marker_ray` gives. The marker on the diagonal is never nearer than both line partners, so leaving it out changes no output.
- Deletions:
    - Removed: the `p` and `d` columns of `gap_cell`, and `marker(P, _)` in the `$NearestMarkerColor` ring clause.
    - Kept: the pairing atoms of `gap_cell`. On four markers, the geometry already gives the pairing, but those atoms state which two gap ends make one side.
    - Kept: `background_defect`. It states that the color is the commonest on every input.
- Lint hint `negated-use`: applied, so `dot_color` in Determine negates `ex_in` directly.
- Name: the type is `DotReach` and not `Reach`, because `Reach` is a lib component name.

## Unsettled
- The runner reports that no run shows `$CappedReach & background=stored` or `$CappedReach & $UnclippedArm & background=stored` defined and differing from its `background=DominantColor` version. I found no such input. With four markers, the stored background is the commonest color wherever these cases are defined. The handbook gives no directive that drops the stored-branch cases of a `@derive` point. What would settle it: a directive for that, or a ruling that these cases stay.
- `dot_spacing` and `reach_cap` have no determination relation. The plan reported the enumeration over its limit (1083 > 100) and listed both. A determination of the dot length and gap from train outputs would settle it. Such a determination needs run lengths along each side, through `Ray` and `Tally`.
- `deletions` ran before the last two edits. Those edits were the column and atom removals it reported, and the `negated-use` fix. A new `deletions` run would settle it.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/f35d900a/analyze.md`, the Not formed line "A derived `reach_cap`, `partner_axis` or dot period: no proposer gives a number…": this is wrong for `reach_cap`, because `derive` finds 7 proposers that fit. The line should name them, and SepThickness should be a branch.

## Tickets filed
- none
