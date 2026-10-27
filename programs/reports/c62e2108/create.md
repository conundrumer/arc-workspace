# c62e2108

## Departures
- `record --all` renamed the witness file's groups to the concept constructors (`$Overwrite`, `$ToEdge`, `$Translate`, `$Adj4`, `$EveryLined`, `$KeepMarkers`) and to `marker=stored` and `background=stored`. Under the form that the Witness file section gives, those are the names of the concept branches.

## Judgments
- Lining up: marker M lines up with square S toward D when M's box is one line across D (a cell of M lies on both of its box's edges on D's axis), the two boxes share both margins across D (`dist_pair`), and M lies K > 0 cells past S's box toward D. This is the probe's test. The marker does not need to touch the grid edge, so on `interior-marker` the concept repeats over the marker, as the Analyze file gives.
- Copies: a ray goes toward D from each cell on the tile's edge away from D. `stride` over the ray distance, with the tile's extent and `gap`, gives the copy index and the cell index within the copy. `$Mirror` gets the edge each copy counts from with a `CycleWalk` over D and its opposite. `axis_dim` of `P_t` gives the tile extent.
- Hints: lint `lib-idiom` proposed `same_line` for the two boxes, and I did not use it, because on Boxes it tests one margin only (ticket 10-729). I resolved the case-section hints: I keyed `Ray` and `CycleWalk` on `Dir`, and made `past` read `lined` in place of `hit`, so each case reads only its own branches' facts. I applied the `negated-use` hint in Determine.
- Performance: in the first form of `out`, `shown.value` was read through a record key under negation. That form took 26 s on test 0 and hit the runner's 20 s limit. The flat relation `written` brought a full run down to about 2 s.
- Cases: `impl_choice` holds all 64 combinations of the six points. The Analyze report gives every pair of branches as fitting. No item under Not formed was formed, because the pairs separate each of them, so each fails Fit.
- `derive` listed `background=DominantColor` and `marker=RarestColor`. Both are `@derive` lines, with the Analyze report's plausibility and verdict (`borderline concept`, `ordinary concept`). `store` listed no value that a case can take.
- Determine: `background` is the commonest color of every train input. `marker` is the color of the train inputs that no train output shows, which is a test on the outputs alone. A first form, "no train output keeps a cell of it", got a determine-prediction hint, because it read inputs and outputs together. `gap` has no determination relation, because the plan's proposer for it is the type's own domain (`enumerable(25)`, `pairs-exact: (0)`), which derives it from no fact.
- Deletions: none of the 34 deletions that change nothing was made. Each of them removes one of these: a branch's clause that only the witness grids exercise, a scene test the pairs always meet (thin markers, `background` and `marker` exclusion), or a join key (`s`, `d`, `n`) that the pairs do not separate.
- Keywords: `objects markers cast bbox`.

## Open
- The audit's store check skipped `painted`, `shown.item`, `shown.value` and `written`, because each has over 20000 rows on an input. A store check that handles that size would settle it. Each of those relations holds facts per case and per cell.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- 10-728_task_c62e2108_create.md
- 10-729_task_c62e2108_create.md
