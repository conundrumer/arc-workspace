# b15fca0b

## Departures
- The cases are the concept case and the eight combinations of `Cost` × `Passable` × {`$TieAny`, `$TieUnion`} that take `$NoRouteKeep` and `$AllPairs`. `impl_choice` excludes the other combinations. Those cases fail Subsumption: `$TieAny` or `$TieUnion`, `$NoRouteKeep` and `$AllPairs` only widen where the model is defined. So a case that takes `$Unique`, `$Joined` or `$TwoEnds` and is not the concept case gives, wherever it is defined, the output of the copy that takes the three relaxed branches. As a result, the single-branch models of `$FewestTurns`, `$PassNonWall`, `$TieAny`, `$TieUnion`, `$NoRouteKeep` and `$AllPairs` in the Analyze report are not cases of the solver. `record --all` rewrote the witness file's names to the cases that stand for them. `witness --file work/task/b15fca0b/witnesses.json` reports no difference.
- Both `@derive` lines carry `// @ignore: derive concept`, for the same reason. The concept base with a derived `background` or `endpoint_color` gives, wherever it is defined, the output of its `$TieAny & $NoRouteKeep & $AllPairs` copy.

## Judgments
- `$NoRouteKeep` & `$AllPairs`: a pair of endpoints with no walk paints nothing, and the other pairs are painted. With two endpoints this is `$NoRouteKeep`'s model. This rests on the report's line that the two branches' changes apply together.
- `$PassNonWall` crosses every cell that is neither of `wall_color` nor an endpoint. Endpoints are where walks end, so a walk between two endpoints never crosses a third endpoint. The pairs do not instantiate this. The rule is kept because otherwise `$AllPairs` would let one walk run through another endpoint.
- `$FewestTurns` has a relational form, and is encoded without arithmetic:
    1. `runs` (GraphDistance over straight clear runs from `Ray`) gives the fewest runs.
    2. `run_back` traces back the runs of every fewest-run walk.
    3. A step graph over visits (cell, entry direction) follows only those runs. A visit may turn only where a run of such a walk ends, or at the start.
    4. The fewest-step walks of that graph are the fewest-run walks with the fewest steps.
    - Two such runs in one direction that cover one cell lie in the same run layer, so a visit fixes its layer, and no walk with an extra run gets in.
    - Checked on `turns-vs-steps` and on a 4×4 open grid with one wall cell. On that grid the case gives the two L-shaped walks, and `$Steps` gives the 8 monotone walks.
- `$TieAny` resolutions are one visit per step of each pair's walk, from `TiebreakResolutions`. `broken_walk` drops an assignment whose visits at two steps in a row are not linked by a fewest-step edge. The items are visits, not cells, so a resolution cannot splice two tied walks into a walk with more runs.
- Each two endpoints are taken once through `Canon<Ends>`'s representative. The first draft compared `IdentOf` ids with `<`, and lint rejected it with `typed-order`. Only `$TieAny` needs one direction per pair, because the two directions of one pair must not resolve on their own.
- Lint hints `case section`, on the `$FewestTurns` clauses: the shared `link` head hid the cost key. Writing `$FewestTurns()` into that clause's head cleared them. `enumerator name` on `union_tie` and `shared-read` on `background` were fixed: the first by testing `T != $TieAny()`, the second by moving `background` under `$Background`.
- Deletions removed: `no_route_choice` and `endpoints_choice` (the `impl_choice` disjunction binds both fields), `run.cell` (the program reads only the frame-wide `clear_cast` and `stop`), `way(W)` in `runs.edge`, `pair(A, B)` in the `$Unique` clause, and the `impl_choice` atom in `ties.cand` (every way now has a `$TieAny` case). Deletions kept, because the pairs do not instantiate the structure they guard:
    - the definedness checks (`crowded`, `tie`, `undefined`, the `!undefined` tests)
    - `!params.endpoint_color` in `open($PassNonWall(), _)`
    - `end(Q)` on a run's stop
    - `runs.pred` in `route_leg`
    - `leg_step.p` and `turn_at`, which keep walks to the fewest runs
    - `dir_elem(D2)`, the narrowing atom for 4-adjacency
    - `next`, `broken_walk` and the `!walked` disjunct of `$TieAny`
- Not formed: `derive` lists only `background=DominantColor` and `endpoint_color=RarestColor` as fitting derivations. No `wall_color` derivation fits. Painting the endpoints fails Fit at every pair.
- Determine: `sweep` gives one value for each parameter. `determination-plan` lists no actions, because every value is covered by a built-in derivation. So the solver has no `Determine` comp.

## Open
- `$TieAny` performance: `TiebreakResolutions` enumerates every assignment of visits to steps before `broken_walk` filters it. On an open grid with many tied walks this grows exponentially. The task's inputs and witnesses run in seconds, but a 5×5 open grid with corner endpoints would give around 10^5 assignments. A lib construction that enumerates the source-to-sink paths of a DAG as resolutions would settle it.

## Lib
- Fewest-hop walks between two nodes: the nodes on some fewest-hop walk from a seed to a target. Solver-local form: `GraphDistance` from the seed, then `Propagation` from the target's least-distance nodes back along `pred` (`steps`, `arrival`, `back` here, and `runs`, `run_back`). The grep finds the same shape in `programs/solvers/7b0280bc.dl` (`hops`, `back`), which is a draft.

## Fixes elsewhere
- none

## Tickets filed
- 10-261_task_b15fca0b_create.md
