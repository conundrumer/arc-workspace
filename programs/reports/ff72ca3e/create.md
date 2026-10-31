# ff72ca3e

## Departures
- The solver holds `center_color=RarestColor` as a `@derive` branch, and `analyze.md` says that derivation fails Fit at train1: in the solver, a gray cell that RarestColor takes as a center is also a blocker. Its nearest stop is itself, at distance 0, so it grows no square. `derive` reports that the branch fits every pair, and the pairs run passes with it.
- The `centers-block` and `cover-centers` witnesses have a group for `center_color=RarestColor`, and their `separates` texts say what that group gives. Each of those inputs has two yellows and one gray, so RarestColor takes gray as the center color and no square grows.
- The edge-limit branch that `analyze.md` calls `concept` is the constructor `$Open`, the blockers branch is `$Gray`, and the center-cover branch is `$Keep`. `record --all` rewrote the witness file's names to those forms.

## Judgments
- Chebyshev distance is a `GraphDistance` over king moves between grid cells, seeded at each center. On a full grid, that fewest-move count equals the Chebyshev distance. The graph holds grid cells only, so a square stops at the grid edge, as `square-radius` requires.
- The square is the set of cells nearer the center than its nearest stop (`Extremes.low`), tested by a bound comparison. `$EdgeBounds` adds the bound that a cell is no farther than the center's nearest edge distance (`dist`).
- `$CentersBlock & $CoverCenters` is left out of `impl_choice`. Under `$CentersBlock` no square holds another center, so that combination gives the same model as `$CentersBlock` and fails Equivalence. The other five bases are cases.
- Under `$Open`, a center with no stop makes the case undefined (`undefined` blocks `keep-rest`). This follows `analyze.md`, which says that the concept is undefined where a center has no blocker.
- The `center_color=RarestColor` witness is train0 with 4 and 1 swapped: `variant derived`, `@relaxed lone-cells`. That input has color-1 cells, so at the stored assignment it breaks `lone-cells`. A recolored variant task would pair it with the squares grown from the 1 cells.
- `fill_color=OutNewColor` does not fit, and `derive` does not list it. So it has no line, which agrees with `analyze.md`.
- Determine: `fill_color` is an output color that no input has. `center_color` is the color of an output cell whose eight neighbors all take the fill color. `blocker_color` is the input lone-cell color that is not the center color. The first version read inputs and outputs together through a recolored-cell test. The `determine prediction` hint fired on it, so the clauses now read one side each.
- The `determine prediction` hint on `blocker_color` remains, because that relation reads the `center_color` determination, which reads the outputs. I kept it with `@ignore`, because the input facts alone give two lone-cell colors, and only the center determination tells them apart.
- `deletions`: a test is kept where the pairs never exercise it but a witness or the model's domain needs it. Those are `in(Q, _)` in `king_step` (no off-grid square cells), the `undefined` clause and its negation (the domain where a center has no stop), the `$CentersBlock` stop clause (the `centers-block` witness), and `impl_choice` in the `$CoverCenters` paint clause (it leaves out the combination that is not a case). `dir_elem(D)` in `clumped` stays, because it limits the lone-cell test to cardinal neighbors. The redundant `impl_choice` atom in the `$Keep` paint clause was removed.
- Keywords: `markers` (the yellow cells fix the places, and the gray cells fix the extents), `span` (the extent is limited by marks), `rank` (the nearest stop is an extremum).

## Unsettled
- `deletions` ran before the last two solver edits: the removal of the `$Keep` paint clause's `impl_choice` atom, and the removal of the unused `blocker-near` header line. After those edits, the pairs run and `witness` pass. A `deletions` run on the final file would settle it.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/ff72ca3e/analyze.md`, the `center_color=RarestColor` line: it says the derivation fails Fit at train1. That holds only for an encoding where a gray center grows a square. If a gray center is its own stop, it grows nothing, and the branch fits.

## Tickets filed
- none
