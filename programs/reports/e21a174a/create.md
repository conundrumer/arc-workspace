# e21a174a

## Departures
- The concept's `disjoint-bands` check tests band overlap, not shared lines. A layer is undefined when a cell of another layer lies inside its band, between its first and last line: `analyze.md` and `repeated-color` make the concept undefined where one color's band covers another layer, and that layer shares no line with the color.
- The witness file adds `unstacked=stored`, which `store` built from train 0 turned a quarter turn. The concept is undefined there. `$AxisFromInput` reverses the layers along H. `unstacked=stored` gives the input unchanged. The `repeated-color` separates text now names `unstacked=stored`, which gives the input unchanged there too.
- `store` proposed a `@store` on `mixed_line[a]`, the axes with a line of two colors. That relation held the lines as well, so it was not one value on every input, and the relabelings check failed on it. I put the test into the `$RowRuns` clause of `unstacked`, and `unstacked=stored` covers it. With that test in `unstacked`, `$RowRuns` no longer drops two-color lines from its run nodes. That input is undefined in any case.

## Judgments
- `$AxisFromInput` gives one grid per axis that has disjoint bands. The axis goes in a `TiebreakResolution = [stack_axis: Axis]` column so that `diagonal-stack` can give two grids. The concept facts hold their stored axis in that column. The rule "No parameter stores the resolution values" reads at best loosely on this: the concept's `stack_axis` value fills that column.
- `@store` on `unstacked`: `variant $AxisFromInput`, `@relaxed disjoint-bands`. The witness is a rotated train input. A rotated variant task gives it routinely and reverses it along H.
- `head-zero` hint on `span($FrameMirror(), ZERO)`: kept with `@ignore`. ZERO is the whole frame, which is the box that `$FrameMirror` mirrors within.
- Case-section hints on the first draft: I gave `layer` a top-level `LayerUnit` column in place of a `LayerKey` record, and the hints cleared.
- The `common-subexpr` hint: I merged the two `out` clauses into one disjunction. The `negated-use` finding: I dropped `moved_at`.
- Determination: the plan asked for `background`. I wrote it in `Determine` as the color that is commonest in every train input, with `Mode`. `stack_axis` stays covered by enumeration, since no proposer derives it.
- `deletions`: 8 removals change nothing on the pairs. Each one is either the band-overlap or two-color-line test that the witnesses use, the `layer` atom and `split` atom that bind a cell to its layer, or the train-only and defect-negation form of the determination. None was removed.
- Keywords: `color-class lines permutation move`.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
