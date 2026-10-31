# df9fd884

## Departures
- The `$EachObject` branch's model (`$EachObject` with `$MatchMouth`) is not a case. `impl_choice` pairs `$EachObject` only with `$KeepOffsetInMouth`. For that reason, `witness --file programs/reports/df9fd884/witnesses.json` reports that `$EachObject` denotes no case in the groups of every Analyze witness: the case fails Subsumption. Where every object's span equals a mouth, containment gives the same entry cup. The only extra entry needs a mouth wider than the object, and then the mouth-to-mouth shift is no translation. So no input shows `$MatchMouth & $EachObject` defined and differing from `$KeepOffsetInMouth & $EachObject`.
- `$KeepOriginal` and `$MirrorAcross` have no constructor: `analyze.md` gives them no witness, and both fail Fit.
- The witness file has two witnesses that `witnesses.json` does not have:
    - `trip=stored`, which `store` built (train0 turned a quarter turn).
    - `split-object`, which I built (see Judgments).

## Judgments
- `trip` `@store` (axis of the mouths and exit direction, `(AXIS_V, DIR_B)` on every input): held as a branch because `store` printed a line to add for it. Its witness is train0 turned a quarter turn. `variant concept`: a rotated task is a variant task, and the concept derives the axis from the mouths.
- `// @ignore: store $KeepShape`: under `$KeepShape`, the flip is the only reader of the stored axis. Each `trip=stored` case is then equivalent to the case that slides toward `params.fall_dir` (`$StoredDirection`). No input separated `$StoredDirection & trip=derived` from `$MouthFacing & trip=stored`, so those cases fail Equivalence. The two cases took equal counts of non-concept branches, and I removed the stored ones.
- `split-object` witness (train0 with the object cut into two cells that touch at a corner, (4,6) and (5,7)): it shows `$OneObject` defined and different from `$EachObject` under `$StoredDirection` and `trip=stored`. `borderline concept`, `@relaxed one-object`. The object is no longer connected, and a reader would still move the two cells together through the cup whose mouth they span.
- `@derive DominantColor` on `background`: `variant derived`, from `derive`. Its witness is the Analyze witness `background=DominantColor`.
- The concept takes the object to be every cell that is neither background nor cup color, as one unit. Under `one-object` this is the same as one component, and it keeps the concept apart from `$EachObject`. The concept is undefined where the object has no entry cup: the object's cells then get no `out` fact. This gives the undefined outputs that `witnesses.json` records.
- The entry test is relational: the lines that the object and the mouth span across the facing axis, compared by defect negation (`overhang`, `underhang`). The cross is the across part of the shift between the two mouth boxes. The slide is `jump_offset` by the moved box's distance to the edge (`$ToEdge`), or `Gravity` with non-background cells blocked (`$StopAtObstacle`).
- `$CupByShape` cup test: a one-color component whose bounding box has gap cells only on one side, none at a corner, and whose opposite side lies on the grid edge. This reads `cup_depth` = 1 from the scene.
- Determine: `background` is the commonest color of every input. `cup_color` is the color other than the background that every input holds (inputs alone). `fall_dir` is the edge that the non-background, non-cup cells touch in every train output (outputs alone). The first `cup_color` form read inputs and outputs together, the `determine prediction` hint fired on it, and I rewrote it.
- Hint `common-subexpr` on `stray_gap`: I merged the two clauses into one disjunction.
- Finding `dead: count_choice`: I removed the enumerator, because `impl_choice` names the `Count` constructors directly.
- The audit reported no stored fact whose removal changes nothing, and it skipped no check.
- `deletions`: I kept all 23 deletions that change nothing. Each one states structure that the pairs never instantiate: the object-at-mouth tests, the cup-shape test, the obstacle set, undefinedness where there is no trip, and the determination defects. One removal, the extra `cup_box.box` atom in `trip`, was implied by `facing`. I removed it before the last run.
- Keyword `continue`: the object leaves through one cup and continues through the other, so the two mouths are linked.

## Unsettled
- What `trip=stored` gives at `$FlipShape` on an input with horizontal mouths and an asymmetric object: no witness shows a `$FlipShape & trip=stored` case different from `$FlipShape & $StoredDirection`. Neither case is among the witnessed cases now. A `witness` run that lists them would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
