# b15fca0b

## Departures
- The cases are the concept case and the eight combinations of `Cost` × `Passable` × {`$TieAny`, `$TieUnion`} that take `$NoRouteKeep` and `$AllPairs`, so the single-branch models of `$FewestTurns`, `$PassNonWall`, `$TieAny`, `$TieUnion`, `$NoRouteKeep` and `$AllPairs` in the Analyze report are not cases of the solver (create): `$TieAny` or `$TieUnion`, `$NoRouteKeep` and `$AllPairs` only widen where the model is defined. The departure holds: `witness b15fca0b --every-case` reports each dropped single-branch case as failing Subsumption, and `witness --file work/task/b15fca0b/witnesses.json` reports no difference.
- Both `@derive` lines carry `// @ignore: derive concept` (create): the concept base with a derived `background` or `endpoint_color` gives, wherever it is defined, the output of its `$TieAny & $NoRouteKeep & $AllPairs` copy. The departure holds, and `audit` reports `derive: ok`.

## Judgments
- `$NoRouteKeep` & `$AllPairs`: a pair of endpoints with no walk paints nothing, and the other pairs are painted (create). With two endpoints this is `$NoRouteKeep`'s model.
- `$PassNonWall` crosses every cell that is neither of `wall_color` nor an endpoint (create): a walk between two endpoints never crosses a third endpoint, which `$AllPairs` needs.
- `$FewestTurns` has a relational form, encoded without arithmetic (create): `runs` gives the fewest straight runs, `run_back` traces the runs of every fewest-run walk, and a step graph over visits (cell, entry direction) follows only those runs, so its fewest-step walks are the fewest-run walks with the fewest steps.
- `$TieAny` resolutions are one visit per step of each pair's walk, and `broken_walk` drops an assignment whose visits at two steps in a row are not linked (create). The items are visits, so a resolution cannot splice two tied walks into a walk with more runs.
- Each two endpoints are taken once through `Canon<Ends>`'s representative (create).
- Simplify: the `turn_at` rule for the walk's start was redundant. `steps` seeds a visit at the start endpoint in every direction, so a walk's first run already leaves from the seed visit of its own direction. With that rule gone, `turn_at` was `route_leg` alone, so it is inlined into the `$FewestTurns` `link` clause, and that clause's `dir_elem(D)` is dropped because each disjunct grounds `D` as a `Dir`. The solver, `witness` on both files, and `witness --try` on a 4×4 open grid with one wall cell give the same outputs as before.
- Deletions kept, because the pairs do not instantiate the structure they guard (create, carried for those that remain): the definedness checks (`crowded`, `tie`, `undefined`, the `!undefined` tests), `!params.endpoint_color` in `open($PassNonWall(), _)`, `end(Q)` on a run's stop, `runs.pred` in `route_leg`, `leg_step.p` and the `route_leg` test in `link`, which keep walks to the fewest runs, `dir_elem(D2)` in the `$Steps` `link`, the narrowing atom for 4-adjacency, and `next`, `broken_walk` and the `!walked` disjunct of `$TieAny`.
- Prune: the `impl_choice` comment named only `$TieAny` as the subsumer's tie branch. It now says the subsumer takes `$TieAny`, `$NoRouteKeep` or `$AllPairs` in place of each concept branch the case takes.
- Checks: the solver passes every pair with 11 witnessed cases, lint is ok, and the audit reports no finding.
- Determine: `sweep` gives one value for each parameter, and `determination-plan` lists no actions (create).

## Open
- `$TieAny` performance (create): `TiebreakResolutions` enumerates every assignment of visits to steps before `broken_walk` filters it, which grows exponentially on an open grid with many tied walks. A lib construction that enumerates the source-to-sink paths of a DAG as resolutions would settle it.

## Lib
- Fewest-hop walks between two nodes (create): the nodes on some fewest-hop walk from a seed to a target. Solver-local form: `GraphDistance` from the seed, then `Propagation` from the target's least-distance nodes back along `pred` (`steps`, `arrival`, `back`, and `runs`, `run_back`). The grep finds the same shape in `programs/solvers/7b0280bc.dl` (`hops`, `back`), which is a draft.

## Fixes elsewhere
- none

## Tickets filed
- none
