# cc9053aa

## Departures
- `$HazardSide` is a constructor, though `analyze.md` gives it no witness of its own: `analyze.md` line 41 says `$HazardSide & $RouteFewestTurns` and `$HazardSide & $RouteTieFewestTurns` fit every pair, and the Coverage goal wants a case for each model that meets the case conditions. `impl_choice` leaves out the combinations of `$HazardSide` with the other three routes, which fail Fit at test0. Its `@witness` line is `diagonal-hazard`, which I built.
- `$HazardCellOnly`, `$HazardRoom`, `$RouteReachable` and `$RouteOuterBoundary` have no constructor. Each fails Fit alone, and in every combination, at the pair `analyze.md` gives (train0, train2, train0 and train2), and `analyze.md` gives none of them a witness.
- The witness file has two witnesses that `witnesses.json` does not have. `diagonal-hazard` is the witness `$HazardSide`'s `@witness` line needs. `edge-wall` answers the audit report that no run showed `$MarkerGiven` defined and differing from `$MarkerColorEdge` when both take `route_color=stored`. Run with `--file` against `witnesses.json`, the solver gives every group's grid (`witness: ok`).

## Judgments
- The route is walked marker to marker. The walk's cells are the clear wall cells plus the markers, and only the route's wall cells are painted: under `two-markers` each marker touches exactly one wall cell, so the fewest-hop marker-to-marker walk is the contact-to-contact walk with a marker at each end. This also lets turn counts include the step from each marker into its contact, as `analyze.md` defines them. Leaving the markers unpainted keeps them 9 under `route_color=stored`, as the `route_color=stored` witness wants.
- Tied walks each get their own output through a `TiebreakResolution` column. `TiebreakResolutions` gives one cell per hop count from a fewest-hop predecessor DAG of `GraphDistance`, and a resolution in which some cell has no predecessor in the same resolution is dropped. `$RouteTieUnion` and `$RouteAnyWalk` give one grid under `$End()`. Each trip runs from one of the two markers, so every walk shows up twice, once from each end. The two copies paint the same grid, which avoids choosing one end.
- `$RouteAnyWalk` has a relational form. By Menger, with a sink joined to both markers, a cell lies on some simple marker-to-marker walk exactly when no single other cell, once cut out, leaves it reaching neither marker. This is coded as `Reach<Cut>`, one instance per cut cell, plus a `Components` test that the markers are joined.
- `$RouteFewestTurns` works on a leg graph. Its nodes are (cell, axis of the last leg), and each edge turns and runs straight (`Slide`). A marker seeds both axes. The fewest legs give the fewest turns, shifted by one for every walk alike. A fewest-turn walk cannot cross or reuse a line: a shortcut would save turns. So the walks are simple, and a cell names its leg's end unambiguously.
- `route_color` is derived from the color of the marker cells, not as `marker_col` renamed. That rename is an `alias-inline` lint finding, which `@ignore` cannot dismiss. The relation holds the `@store: ordinary stored` line that `analyze.md`'s `route_color=stored` branch needs. `store` reported only "stored already" for it, and Develop step 4 holds it anyway.
- `store` proposed `@store` lines on `commonest.mode`, `wall_pick.item/value`, `edge_ink.item/value` and `rest.item/value`. Each is dismissed with `@ignore … store`: a stored value there is the stored role color of the matching `Given` branch, so the case fails Equivalence.
- `derive` offered `marker_color=DominantColor`, `SharedColor` and `VanishedColor`, but its runs were killed (exit -9) and it judged none of them. I dismissed them with `@ignore: derive` lines. DominantColor gives 0, which makes every background cell a marker. SharedColor gives every input color. VanishedColor, with `ex_out` empty, does the same. Each fails Fit at train0.
- Hints: I inlined the single-consumer `outcome`. The common-subexpr hint on `cut_off` is resolved by reading `uncut.node`. The `determine prediction` hint on `hazard_color` is ignored: the wall and marker colors it excludes are read directly from the repainted cells, not guessed.
- Determine: `wall_color` and `marker_color` are the input and output colors of repainted cells. `bg` is the commonest color of every train input. `hazard_color` is the input color left over. The sweep finds each value unique, and the plan lists no actions.
- Deletions: the atoms that change nothing are tie, disconnection and turn structure that the pairs never instantiate, and witnesses exercise them. The `impl_choice` atoms keep non-case `Choice` values out of `out`. `wall(W, P)` in `paint` matters under `route_color=stored`. I removed only the redundant `ex_out` atom from Determine's `commonest.item`.
- Witness `diagonal-hazard`, ordinary, verdict concept: a hazard in a room touches a turn of the shorter L route only at a corner. It breaks no scene claim, and the concept's clear cells still hold one route. Test0 shows that diagonal hazards close walls.
- Witness `edge-wall`, variant, verdict concept: train0 with one wall line reaching the grid edge. It breaks no header claim, but no example's walls reach the edge. The markers are the given 9, so the concept's output stands.
- Not formed items of `analyze.md`, each formed and dropped under Fit, so no constructor:
    - hazard reach of radius 2 closes contact (1,4) at train2;
    - keeping every hazard on one side leaves no route at train2;
    - the `ex_out` proposers are undefined at every pair;
    - no count rank gives one role color on every input.
- The built-in derivations that `analyze.md` lists for `wall_color`, `marker_color` and `hazard_color` fail Fit at train0, as it states.
- Performance: `TiebreakResolutions` builds every combination of a slot's candidates before the predecessor filter, 2^11 per trip on the `tied-routes` ring. Its `assign` passes 20000 rows, so `store` skips `walks.assign`. The run itself takes about 7 s.
- Keywords: `markers route rank`. `rank` covers the fewest-turn extremum and the commonest color.

## Unsettled
- The audit's store check skipped `walks.assign` (over 20000 rows on an input): this would be settled by a store check that handles enumerated resolutions, though no stored value is plausible there.
- `derive` cannot judge the three `marker_color` derivations because their runs are killed (see `progress-create.md`): this would be settled by a derive run with a row or time cap that reports a run it stops as failing Fit.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
