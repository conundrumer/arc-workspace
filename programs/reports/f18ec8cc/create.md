# f18ec8cc

## Departures
- The `$SolidLines & $Cycle` case, which is the model of the `$SolidLines` branch, is left out of `impl_choice`. It fails Subsumption against `$SolidLines & $RotateColumns`, as `analyze.md` states. For this reason, `witness --file programs/reports/f18ec8cc/witnesses.json` reports that `$SolidLines` on `tie-in-first-stripe` and `tie-in-later-stripe` denotes no case. On both witnesses, the remaining `$SolidLines` case gives the grid that `witnesses.json` gives.
- The witness file adds `edge-dots-first-stripe` and `mixed-later-run`, both `borderline concept` with `@relaxed dots`. In both, every line of the first stripe holds a dot, so no line of it is solid. `edge-dots-first-stripe` separates `$Commonest & $RotateColumns` from `$SolidLines & $Cycle`, a pair that `witness` reported no run separating. `mixed-later-run` makes `$SolidLines & $RotateColumns` a witnessed case: its last run holds solid lines of 1 and of 3, so `$SolidLines & $Cycle` is undefined there, and its first run is wider than the concept's first stripe.

## Judgments
- Stripes are found through cuts between adjacent lines, in both parses. The concept parse cuts between adjacent lines whose unique commonest colors differ. On inputs with no tie, this gives the maximal runs of `stripes`. A tie line makes the stripe that holds it unreadable (`bad`). A line's stripe index is the count of cuts between it and the `from` edge (`Tally`). That count is a rank, so the index needs no arithmetic.
- `$Cycle` walks the stripe indices around a cycle `shift` steps toward `from` (`CycleWalk`). It then orders the lines by slot and by place in the stripe (`Order`, score form). The rank is the line's output distance from `from`. `$RotateColumns` walks the lines around a cycle by the combined width of the first `shift` stripes. Each rearrangement is undefined where its parse cannot read a stripe that the rearrangement reads: every stripe for `$Cycle`, and the first `shift` stripes for `$RotateColumns`.
- The Determine relation `shift` finds, in each train pair, the input line nearest `from` that equals the output's line at the `from` edge. It then counts the distinct solid-line colors before that line. The `determine prediction` hint on `shift` is kept with `@ignore`: the value is read from the evidence, and is not a guess that a test keeps. `from` has no relation, because the plan covers it by enumeration (one of 4 values reproduces every pair).
- The sweep reports that `shift` = 13 also fits under `$Cycle`. It is not stored, because `analyze.md` gives 1 as the only value a reader takes, so `shift` is no open parameter.
- The Not formed item "Stripes as 4-connected regions" is not formed as a branch. The item does not say which regions are stripes, because the dots are regions too. So it states no single model.
- `derive` found no built-in derivation, and `store` printed no line to add. So no `@derive` or `@store` branch is held.
- `cell_line` moved into `Parse<Key>`, because Determine repeats it over `ex_in`. The solid-line `Unanimous` in Determine is keyed by `ExampleLine` and stays there. A generic `Parse<Key>` cannot form the compound key that the program's Position-keyed instance would need.
- The kept `deletions` findings: the `bad`, `bad_moved` and `run_color` rules, with their negations, give the undefined outputs that the witnesses show. The `impl_choice` atoms leave out `$SolidLines & $Cycle`. `dist(L1, D, 0)` limits the wrap edge to the edge stripe. `ex_out` in `lands_at_edge` and `shift_contradicted` limit the determination to the train pairs and to their agreement. `passed.domain` gives 0 where the output leads with the input's first line.
- Witness judgments: in `edge-dots-first-stripe` and `mixed-later-run`, the 5 stripe is plain from each line's commonest color. So the generator would move that stripe alone, and the verdict is `concept`. The dots on the edge lines break `dots`, so plausibility is `borderline`, the same level as the Analyze witnesses.
- Keywords: `lines` (per-line commonest color and solid lines), `permutation` (the stripes reorder by a cyclic shift), `noise` (the dots are ignored by the parse and carried with their stripe).

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
