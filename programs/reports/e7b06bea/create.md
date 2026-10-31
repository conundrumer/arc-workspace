# e7b06bea

## Departures
- The concept's background parameter is named `background`, as the concept file names it. The `derive` run first wrote a witness `bg=DominantColor` under the old name. That witness was removed, and the analyze witness `background=DominantColor` is the witness that `derive` now records for the `@derive DominantColor` line.
- The witness file's names are rewritten by `record --all` into the solver's forms, for example `$StoredStart & $EdgePhase`, `$LineStripes`, `$StoredStripeEdge` and `background=stored`. The grids are the same as in `witnesses.json`.
- The concept case is undefined where the bar lies on the folded line, because there the cell gets both the bar color (`keep-bar`) and a run color. Every case is also undefined where its start edge is undefined. Both rules make the solver give the undefined outputs that `witnesses.json` gives on `background=DominantColor`.

## Judgments
- `background` gets a `@derive DominantColor: variant derived` line, with `@relaxed background-field`. The plausibility and verdict come from the analyze witness `background=DominantColor`.
- `bar_end.item` and `bar_end.value` have `@ignore ...: store` lines. A stored start edge is the concept branch `$StoredStart`, so the stored branch fails Equivalence with the concept case.
- `impl_choice` leaves out `$DerivedStart & $BarPhase`. As analyze.md states, a derived start edge means that the bar starts at that edge, so that model is the model of `$DerivedStart`. It fails Equivalence.
- Hints. `common-subexpr` on `stripe_cell`/`fold_cell` is resolved by a shared `line_cell` relation. `single-consumer` on `has_fold` is resolved by inlining. `common-subexpr` on `unit_next` and on `back_index` is kept with `@ignore`, because the shared atoms find different lines and count in different directions.
- `Determine.background` reads the background from the output's line at the stripe edge, which `clear-stripes` clears. `start_edge` and `stripe_edge` are determined by enumeration of their domain. The plan asks for no relation for them.
- `deletions`: the atoms it lists as changing nothing are guards that make a case undefined, the claims `edge-stripes` (the seed line at the edge, the axis of the nodes) and `first_unit`, or clauses of the `$BandStripes` and `$BarPhase` branches. The pairs instantiate none of these, so all of them stay. One atom, `opposite(D, D_in)` in `stripe_line`, was redundant because `block.run` binds the direction, so it was removed.
- Keywords: `lines` (stripes are lines), `markers` (the bar fixes the run length), `count` (the bar's length sets the extent of each run).

## Unsettled
- `deletions` ran before the last solver edit, which removed `opposite(D, D_in)` from `stripe_line` and changed comments. A `deletions` run on the final file would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
