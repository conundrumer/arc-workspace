# fe9372f3

## Departures
- The solver adds the case `$PlusByColor & plus_color=RarestColor` (`// @derive RarestColor: variant concept`, `@relaxed one-plus`), which `analyze.md` does not give: `run_dl.py derive` reports that RarestColor fits `plus_color`, and Develop step 4 holds each built-in derivation that fits. Its witness `plus_color=RarestColor` (train 0 with 2 and 3 swapped) was written by `derive`. On that witness the case gives the concept's output and `$PlusByColor` returns the input. I judge the plausibility `variant` (a recoloured plus is a routine variant task) and the verdict `concept`.
- The solver adds the relations `anchor` and `origin`, for the cell that a dash count starts from and the first cell of a diagonal ray. Under the concept these are the tip and the cell one diagonal step from the center. They are the encoding of `$PhaseFromCenter` (the count starts at the first arm cell) and `$DiagFromCorner` (the ray starts at the cell level with the two tips). `run_dl.py witness --file programs/reports/fe9372f3/witnesses.json` reports no difference.

## Judgments
- Design: the cases are the 32 combinations of five record fields (`Phase`, `Period`, `DiagOrigin`, `RayStop`, `Locate`), together with the `@derive` branches on `background` and `plus_color`. Every combination fits every pair. The runner reports 8 witnessed cases: the concept, one case per branch, and one case per `@derive` line. The witness file covers each of them, and `witness` reports no unseparated pair and no unwitnessed case.
- `background` is under the marker `$NonBackground, $HaltAtObstacle`: the `shared-read` finding showed that `$ToEdge & $PlusByColor` never reads it. This matches the `plus-locator` & `background` line of `analyze.md`.
- The hint that `$HaltAtObstacle` and `$ToEdge` may read each other's `spoke` rows came from `dash_walk.step`, which read `spoke` across the stop column. The step counts now come from `spokes.cast`, which does not depend on the stop, and the hint is gone.
- `determination-plan` also lists `accent_color`, `dash_color`, `diag_color` (AnyOutNewColor), `background` (DominantColor) and `plus_color` (RarestColor) as covered. I wrote no relation for them. Each proposer derives its value from the fact the concept reads it from: the field is the commonest colour, the plus is the rarest, and the ray colours are the colours new in the output. `dash_pattern` has a determination relation: the shortest period that no train ray breaks, read from the cell next to each tip.
- I kept the deletions that `deletions` reports as changing nothing. The `blocked` rules and the `!diags.blocked` test serve `$HaltAtObstacle` alone, and the pairs have no obstacle. The `anchor.c` column and the `anchor`/`parse.tip` atoms in `spoke` keep each tip with its own center when an input has more than one plus. The tip marks of `spokes` and the `spoke.d` column serve `$PhaseFromCenter` and `$PeriodFromSpan`. `span.blocked` stops the span at the end of the plus. I removed two deletions: the `parse.center` atom in the `$DiagFromCorner` origin clause, which `parse.tip` implies, and the `ex_out` atom in the Determine `parse.plus` clause, which `ray_col` already makes.
- Keywords: `objects` (the plus), `cast` (the rays), `wallpaper` (the dashed ray is a periodic pattern along one axis).
- Under `$HaltAtObstacle`, a diagonal origin that is not background casts nothing. This is the reading of "stops before the first input cell that is not background" for a ray that starts on such a cell.
- I piped the output of one `record --all` run to `grep`, against "Reading files and outputs". The lines it dropped were grid rows, and the later `witness` and `audit` runs, read whole, show the recorded file.

## Unsettled
- The audit skipped no check.
- `sweep` reports 47 single-row changes of `dash_pattern` that give every train output. These are longer or sparser spellings of the same period-3 pattern. `analyze.md` gives no open parameter, and the Determine relation keeps the shortest period. A sibling task with a different pattern would show whether the shortest period is right.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
