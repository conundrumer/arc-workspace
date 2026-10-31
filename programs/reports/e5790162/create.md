# e5790162

## Departures
- The `start-count` choice point and `$SingleStart` are not in the solver. The witness `two-start-cells` is not in the witness file: `$SingleStart` fails Subsumption. No input shows it defined and differing from `$EveryStart`, and `witness` reported this. With it gone, `two-start-cells` separates no cases. `witness --file programs/reports/e5790162/witnesses.json` reports that the name `$SingleStart` denotes no case of the solver under every witness, and this departure is the cause.
- The concept branches have names of my own: `$StoredDir`, `$StoredColor`, `$TurnAgain`, `$CrossTrail` and `$PassNonMarker`. `record --all` rewrote the witness groups to the names the solver uses.
- The solver holds a branch that `analyze.md` does not give: `background=DominantColor`, a `@derive DominantColor: variant derived` line with `@relaxed start-cell`. `derive` reported that it fits, and its witness is train0 with 0 and 1 swapped. The judgment is `variant`, since a color permutation is a variant task. That witness breaks `start-cell` under the stored background 0. The verdict is `derived`, since the line runs over the 1 cells in the permuted task.
- `turn-frame`/`$AbsoluteTurn` has no constructor: it fails Fit at train1 (`analyze.md`). `path_color=SharedColor`, `RarestColor` and `DominantColor` have no `@derive` line: they fail Fit at train0, and `derive` did not list them.

## Judgments
- The walk is a `Propagation<Choice, Walker>` over (cell, heading) states. A marker ahead gives an edge that turns in place, and a passable cell ahead gives an edge that steps onto it. The walk is deterministic, so each state has at most one edge out.
- `$StopWhenBlocked` stops the line by taking away the second turn at a cell. The painted cells are the same as when the line stops after the first turn.
- `$StopAtTrail` needs the order of the walk. The edges that a recursive "already visited" test would need are banned, so a `GraphDistance<Line, Walker>` gives each state's step count per start cell. A crossing is a step at count k onto a cell reached at count k or less. The states past the first crossing are cut, by defect negation. Each start cell is its own key, so one line's crossing does not cut another line.
- `$HeadTowardMarker` uses `Ray<Position>` keyed by the start cell, with the markers as blocked cells, and takes the nearest stop through `ArgExtremes`. A tie, or no stop, gives no single heading, so that case is undefined.
- Undefinedness: a case writes no `out` facts where it has no line color (`$StartIsNonMarker` with zero or two plain colors), or where some start cell has no single heading.
- `store` hints on `plain.item`, `plain.value`, `sight.stop`, `nearest.cand` and `nearest.low`: each one is recorded with `@ignore ... store`. Storing any of them gives a model that is equivalent to `$StoredColor` or `$StoredDir`, and that model takes more non-concept branches, so it fails Equivalence.
- The `determine prediction` hint on `Determine.turn_sense`: it is kept with `@ignore`. The clause reads each sense from a turn of the line in the output. The `!background(Col)` test only stops the cell beside a turn corner from being read as a marker.
- From the `determination-plan` actions, I wrote determination relations for `path_color` (the color the line paints), `background` (the input color under painted cells), `start_dir` (the start cell toward the first painted cell) and `turn_sense`. The next plan run listed no actions.
- From `deletions`, I removed `sight.cell`, because `Ray.stop` does not read the domain, and the `dir_elem(W)` atom in `walk.edge`. The other findings are structure that the pairs do not instantiate: the undefined cases, the crossing cut, the `$StopWhenBlocked` test, the `start(P, C)` that keys the start cells by line color, and the guards on the turn reading in the determination. Those stay.
- Keywords: `markers walk lookup`. `turn_sense` is a lookup table keyed by marker color.

## Unsettled
- The audit's `store` check skipped `walk.edge`, which has over 20000 rows on an input. A store check that can handle relations of that size would settle it.
- I ran `deletions` before the final edit, which applied two of its findings, and did not run it again after that edit. A `deletions` run on the current solver would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
