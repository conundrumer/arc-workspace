# c074846d

## Departures
- The solver adds the branch `background=DominantColor` (`@derive DominantColor` on `background`, under `$PerStick`) with a new witness `background=DominantColor`, which the Analyze files do not give: `derive` lists that derivation as fitting, and Develop step 4 holds each fitting derivation as a branch.
- The witness file's group names are rewritten by `record --all` into the solver's names (`$DirTurn`, `$OnePivotSet`, `$Join4`, `pivot_color=stored`, `background=stored`): the concept branches take constructor names of their own.

## Judgments
- The constructors are `$RotateOffsets` (turn-geometry), `$PerStick` with the nested `$CornerJoin` (stick-scope, stick-adjacency), and the concept constructors `$DirTurn`, `$OnePivotSet`, `$Join4`: the Analyze report gives a witness to these branches alone. `$Reflect`, `$CastToEdge` and `$SweepTrail` have no witness and fail Fit, so they are not formed.
- No item under Not formed is formed as a branch: the room-based turn fails Fit at train0, and a derived `sense` or a different turned-arm color states no model that fits.
- The `arm_color` and `trail_color` derivations get no line: `derive` lists none that fits.
- Witness `background=DominantColor` is `variant`, verdict `derived` (relaxing `pivot` and `blank-field`): its input is `two-sticks` with background 1. The Analyze report judges `two-sticks` `variant` with the per-stick output, and a background color permutation is a variant task, so the generator pairs this input with the per-stick output. That output is the output of the derived branch's model.
- Where a turned arm cell lands on a cell the arm left, the arm color wins, and an arm cell on no pivot's line keeps its color: these follow `probe.py`, the Analyze reading. The pairs give no such overlap.
- `sweep` reports that `background` also admits 3. The value stays 0 alone: 3 is the trail color, which no input holds, so no reader of the concept takes it as the background.
- The first `Determine.pivot_color` ("a kept cell that is not background") drew the `determine prediction` hint. It now reads the color of the cell beside both the arm's first cell and the turned arm's first cell, by cardinal steps, other than the color the turned arm covers. That last test excludes the background cell at the opposite corner, which also borders both cells.
- `deletions` gives 18 deletions that change nothing. All are kept:
    - The pairs hold one stick, so the `$PerStick` stick-label atoms are never tested.
    - The `!painted` negation sets the paint-over-trail order, which no pair tests.
    - The determination atoms state where the pivot sits.
- The header keeps `room-to-turn`: the text of `swing` needs the destination cell to exist.
- Keywords `markers d4 objects`: the pivot fixes the turn's place, the quarter turn is a D4 rotation, and `$PerStick` reads sticks as components.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
