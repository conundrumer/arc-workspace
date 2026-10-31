# f823c43c

## Departures
- The witness file has no `chain-broken-by-noise` witness and no `$PeriodPerAxis` name: `$PeriodPerAxis` left under Subsumption (see Judgments). After that, `chain-broken-by-noise` separates no case, because every other case gives the concept's output on it.
- `noise-of-another-color`: `$IsometryOrbit` is undefined there, while `witnesses.json` gives it the input unchanged. The error is in `witnesses.json`. When no pattern period is shorter than the grid, the period becomes the full extent. Then the `Wallpaper` symmetry test finds many D4 maps and shifts that overlap the frame in only a few matching cells. No cell pair contradicts these maps, so the orbits join cells of different colors, and the output is not a grid. The 0dfd9992 encoding of the orbit model has the same behavior. `record --all` wrote the solver's groups.
- `$PeriodPerAxis`, before it left: where no shift shorter than the extent fit an axis, it took the extent. `OffsetInvariance.min_period` has no candidate equal to the extent. The analyzed model ("the least shift under which every two visible cells that far apart agree") includes the extent with no conditions. Without that fallback, the branch was undefined on `noise-of-another-color`, where `witnesses.json` gives the input unchanged.

## Judgments
- The concept period is encoded as a set of candidate pairs. Each pair is a period on each axis, from 1 up to the extent. A tile place is a pair of `stride` remainders, and `Unanimous` tests that the visible cells at each place agree. The period is the least fitting value on each axis, and that pair must itself fit. Where no such pair fits, the model is undefined. These clauses are the relational form of "shortest on both axes".
- Phases are measured from every edge (both `Dir` on each axis, with `perp_dir`). The classes mod K are the same from either edge, so no hidden orientation comes in. The cost is an 8-fold redundant `place.item`. The pairs run takes under 5 s.
- `noise-by-period`, "a period at most half the grid", is encoded as "every place of the tile along the axis has a second copy" (`stride` copy index `N > 0`). For a period K on an extent n, that holds exactly when 2K ≤ n.
- `$RecolorToBackground`, `$PeriodStored`, `period=Period`, and the `RarestColor`, `DominantColor` and `SharedColor` derivations of `noise_color` are not formed. Each fails Fit, as `analyze.md` gives. `derive` reports that no built-in derivation fits.
- `$PeriodPerAxis` failed Subsumption and left. `witness` found no run where it was defined and gave an output other than `$PeriodJoint`'s. This agrees with the argument in `analyze.md`: wherever the per-axis periods are class-consistent, they are equal to the joint least period.
- The Not formed items of `analyze.md` give no branch. Each is either equivalent to the concept or fails to parse train1.
- `case section` hints on `noise`, `repeated`, `short`, `lone` and `by_period` are kept with `@ignore`. The `wp` instance is keyed by noise color. The static analysis cannot see that each case reads `wp` only at its own noise branch's color.
- The `single-consumer` hint on `orbit_color` is kept with `@ignore`, with the reason the 0dfd9992 precedent gives.
- `store` prints no line to add. The joint period has no witness for `period=stored` on D4 images or color swaps. `analyze.md` gives `$PeriodStored` no witness, because it fails Fit. So no `@store` branch is held.
- `deletions`: 33 deletions change nothing on the pairs. The lines it lists are the hidden-phase branches, the full-extent candidate, the least-pair fit check, the noise-by-period filters and the D2/K2 columns. The pairs do not reach this structure, but the witnesses or the claims need it. All of them stay.
- Determination: `noise_color` is the color an input holds where its output differs (the plan's `ChangedColor`). The plan then lists no actions.
- Keywords: `wallpaper repair noise`.

## Unsettled
- The audit's `store` check skips `orbit.edge`, `place.clash`, `place.item`, `place.value` and `wp.action`, since each has over 20000 rows on an input. A store check that can take relations of that size would settle it.
- One `deletions` run timed out: `least.low([X, D1], K1)` in `period`, on train 0. A run with a longer limit would settle it.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/f823c43c/witnesses.json`, witness `noise-of-another-color`: the group that lists `$IsometryOrbit` and `$PeriodPerAxis` with the unchanged input needs `$IsometryOrbit` moved to a group with grid `null`.

## Tickets filed
- none
