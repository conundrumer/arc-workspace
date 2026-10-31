# db695cfb

## Departures
- The header has no `@scene field-with-single-marks` line: no `@claim` or `@relaxed` line denotes that claim, and no rule text depends on it, so Style's Header rule leaves it out.
- The first item under Not formed in `analyze.md` (each `link_color` cell joins only the next one along a diagonal) has no branch: `analyze.md` shows its model is equivalent to the concept case's, so that case fails Equivalence. The other Not formed items state no model that fits (a hidden `cross_color` cell fails Fit at train0, train1 and train3, and the listed derivations give no value or a non-`Color` value).

## Judgments
- The solver has three choice points with witnesses: `$ExtensionEmits` (emitters), `$CrossStopsAtMark` (cross-extent) and `$LinkOverCross` (crossing-precedence). `Choice` is the record `[e: Emitters, x: Extent, r: Precedence]` over their eight combinations. Every combination passes every pair. Only the concept case and the three single-branch cases are witnessed, because every verdict on the three branches is `concept`, and so each branch is rejected and none requires another.
- The branches that fail Fit in `analyze.md` (`$JoinCardinal`, `$IterateJoin`, `$SixBlocksJoin`, `$LoneRayEmits`, `$CrossBothAxes`, `$LinkOverSix`, and the `SharedColor` and `RarestColor` derivations of both colors) have no witness, so they have no constructor.
- `derive` reports that no built-in derivation fits. `store` prints no line to add: `link.mark`, `cross.blocked`, `link.cell` and `cross.cell` have no witness, and `link.ray` varies by position. So the solver has no `@derive` or `@store` branch.
- Every run of `audit` and `witness`, with and without `--file programs/reports/db695cfb/witnesses.json`, reports `ok`. `record --all` changed no group.
- Determination: `link_color` is the color that every train input holds. `cross_color` is the color, other than `link_color`, that some train output paints over its input. Two earlier forms failed:
    - A first `cross_color` form that kept colors no train output changes also kept the test background `3`.
    - A form that tested `lost` read inputs and outputs together, and lint gave the `determine prediction` hint for it.
  The final plan reports both parameters as determined. This is the third plan run, so the plan was not run again after the hint fix. The pairs run after that fix reports `determination: ok`.
- A version that cast the square lines from the emitters alone gave three `case section` hints, because the shared `cross` instance then reads `emitter` rows of every case. The solver casts from every `cross_color` cell instead, and the `cross_line` clauses select the casts whose source is an emitter of the case.
- `deletions`:
    - The `cross_color` tests in `cross.mark` and in both `emitter` clauses imply each other, since a square line needs both. Both stay, because each states its own claim: what casts, and what emits.
    - `cross.blocked` and `!link_top(P)` in the `$LinkOverCross` clause matter only where a square line meets a mark or another joining line. No pair has such a meeting (`clear-cross-lines`), and the witnesses `stray-mark-on-cross-line` and `cross-line-meets-other-link` show both in use.
- No witness was built in this pass. No hint is left in the final run, and no performance issue came up: the pairs run takes 1 s.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
