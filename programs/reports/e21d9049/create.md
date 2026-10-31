# e21d9049

## Departures
- `$SharedPeriod` has no constructor and no clauses, and its names are removed from the witness file. The condition is Subsumption: `witness` found no run where it is defined and differs from `$StripLength`. This agrees with `analyze.md`.
- `$ColorCycle` has no constructor and no clauses, and the witness file drops `repeated-color-strip`, which separated `$ColorCycle` alone. The condition is Subsumption. The first encoding applied the successor walk only to cells past the strip ends. On the all-ink input (bg 0, field 1), every line is a full strip, so that encoding gave the input unchanged where `analyze.md` gives undefined. A `forked` test then made the case undefined wherever a color has two successors, as `analyze.md` states the model. After that fix, no run showed it defined and differing from `$ShortestPeriod`, so it left.
- `background=DominantColor` is the `@derive DominantColor` line on `bg`, named `bg=DominantColor`. The witness file drops the Analyze witness `background=DominantColor` (field 5), because it duplicates the witness `derive` recorded for that branch (train 0 with 0 and 1 swapped).
- The `separates` texts of `alternating-strip`, `unequal-strips` and `count-period` no longer mention the removed branches. `unequal-strips` stays because it separates `$ColorCount` (undefined) from the concept. It has no `@witness` line, because the `@witness` line it had was on `$SharedPeriod`.
- `witness --file programs/reports/e21d9049/witnesses.json` reports only names that denote no case (`$SharedPeriod`, `$ColorCycle`, `background=DominantColor`). It reports no output difference.

## Judgments
- `bg` determination: the colors that are the commonest color of every input. `determination-plan` asked for it as the fact that `DominantColor` derives the value from. It has no actions now.
- Repetition encoding: `along` gives the distance from a strip cell to a line cell through `relative` and `dist`, the same as precedent 0a938d79. `stride(T, K, 0, _, 0)` tests that the distance is a whole number of periods. This states the rule's "multiple of the strip's length" directly. It depends on no edge, so it adds no hidden orientation.
- Strips: the crossing is the ink cell that has ink neighbors on both axes. Each strip is the crossing and the `Slide` run of ink from it along its axis. Each strip end is the `Slide` rest. `$StopAtObstacle` paints the strip and the `Ray.clear` cells from each end. `$ShortestPeriod` takes the least strip gap whose cell pairs never differ in color, or the strip length when no such gap exists. `$ColorCount` takes the count of distinct ink colors as the period.
- `@derive DominantColor: variant derived`, `@relaxed crossing-strips`: from `analyze.md` (plausibility `variant`, verdict its own branch, breaks `crossing-strips` at bg 0).
- `store` printed no line to add. Every derived value either has no witness or varies by an id that the runner stores nothing under.
- Deletions kept: `crossing(X)` in `strip`, the axis columns of `along`, `period` and `broken`, `broken.k`, the `shortest.cand` gap rule and its `strip` atom, `cast.blocked`, the strip rule of `painted($StopAtObstacle(), _)`, `painted` in `out`, and `uncommon` in Determine. The pairs do not exercise them: the inputs have one crossing, distinct strip colors, no obstacle, and one commonest color. The branches or the concept need each of them. Deletions removed: `strip_size.domain` and `impl_choice` in the painted `out` clause. In both, other atoms already ground the variables.
- Keywords: `wallpaper` (a period covers each line) and `lines` (per-line structure).
- Cases: 5 witnessed cases of the `Repeat` × `Extent` × `bg` combinations.

## Unsettled
- The `deletions` run came before the two removals it reported. A final pairs run and lint passed after those removals. `deletions` was not run again.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- none
