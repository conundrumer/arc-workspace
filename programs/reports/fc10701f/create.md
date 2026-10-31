# fc10701f

## Departures
- The concept branches carry constructor names of this pass: `$BothSides` (gate-sides), `$AnyDistance` (gate-reach), `$CrossLine` (gate-axis), `$Corridor` (stamp-region), `$Paint` (landing). The handbook gives each concept branch a name of the pass's own.
- `record --all` rewrote the groups of every witness into the listed name forms. `witness` with and without `--file programs/reports/fc10701f/witnesses.json` prints no difference.

## Judgments
- Corridor: a `Ray` cast from the mover cells in all four directions, blocked by the target. The corridor is the clear part of each cast that has a `stop`, less the mover cells. The motion direction is the direction of a cast that has a `stop`. This states "the cells strictly between the two blocks along the axis that joins them" with no arithmetic.
- `stamp-gates`: a second `Ray` cast from the gate cells over the path (mover cells and corridor) gives the posts at any distance (`$AnyDistance`). A `Slide` run across the path, followed by one `neighbor` step past the path's side, gives the posts that touch the path (`$AdjacentGate`). `line_axis` gives the cross axis (`$CrossLine`, `$AdjacentGate`) or both axes (`$AnyAxis`). `$BothSides` needs a post toward a direction and toward its opposite, and `$EitherSide` needs one of them. Analyze names lib `Between` for the concept. I used `Ray` because the one-sided and adjacent branches need the post per side, and `Between` gives only both sides together.
- `$TranslateMover` and `$TranslateNear`: the travel length is the cast distance in the `slide` Ray from a mover edge cell to a target edge cell, where the two edges face the same way (the motion direction for `$TranslateMover`, its opposite for `$TranslateNear`). Every mover cell `jump`s by that length. The number counts the cells that the cast crosses.
- The cases are all 36 combinations of the five choice points, times the `background=DominantColor` derive branch. The runner runs the 8 witnessed cases, and all of them pass every pair.
- `@derive DominantColor: variant derived` with `@relaxed two-blocks`, as analyze gives it. `store` reported no value to add.
- The determination reads each color through a rule: `target` is the input color absent from its output, `mover` is the color the target cells take (`land`), `background` is the color the mover cells take (`vacate`), `mark` is the output color its input lacks, and `gate` is the input color left over. The `determine prediction` hint on `gate` is kept with `@ignore`, because the colors it excludes are read from the pairs by rules, not guessed.
- Hints from the first runs: `cross-choice` on a `line_axis` disjunction over choice tags, fixed by one clause per tag. `pass-through` on a `cross_axis` relation, fixed by moving it into `line_axis`. `common-subexpr` on the four `out` clauses, fixed by merging them into one disjunction.
- `deletions`: 27 deletions change nothing. Each removes a structure that only a non-concept case or a non-pair input uses, such as the corridor's `stop` test, the `!mover_cell` exclusion, the `$StampStart` path, the cross-axis restriction, the translate clauses' `motion` and off-frame tests, or the `out` precedence negations. The determination atom `out_color(E, _)` limits `gate` to train examples. All of them are kept.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
