# b548a754

## Departures
- The solver adds a choice point `Body` (which cells are the box), with the concept branch `$AllInk` and the branch `$MultiCellPiece`. That branch reads the box as the one 4-connected piece of more than one cell among the non-background, non-marker cells. It comes from the Analyze report's Not formed item "the box found as the non-background object that holds more than one cell": Develop step 3 forms each such claim, and this one fits every pair and has a relational form. It is not equivalent to the concept, and it is not subsumed: on `stray-cell` it is defined, and the concept is not.
- The witness file holds four witnesses that the Analyze file does not hold. `stray-cell` is the `@witness` line of `$MultiCellPiece`. `touching-marker` shows `$StoredMarker & marker_color=RarestColor` defined where `$LoneMarker` is not. `big-box` shows `background=stored` defined where `background=DominantColor` is not. `field-and-dot` shows the case that takes both `@derive` branches with an output that no case with only one of them gives.
- The solver has seven cases, from three bases: the concept base, `$MultiCellPiece & $StoredMarker & $EachMarker & $CoverDiagonal & $RepeatInnerSlice`, and `$AllInk & $LoneMarker & $EachMarker & $CoverDiagonal & $RepeatInnerSlice`. The `@derive` branches add cases to the second and third bases only. The Analyze report expected more cases: it named only the `$EachMarker`/`$CoverDiagonal` combinations as failing Subsumption. Judgments below gives the other cases that leave, and the condition each one fails.

## Judgments
- Non-concept cases that take `$OneMarker`, `$StraightOut`, or both fail Subsumption. Each such case is defined only where its markers lie straight out from the box. There, the same case with `$EachMarker & $CoverDiagonal` gives the same bounding-box stretch, and that case is also defined on `two-markers` and `diagonal-marker`.
- Non-concept cases that take `$Redraw` fail Subsumption by their `$RepeatInnerSlice` counterparts. Where `$Redraw` is defined, the box is a 1-wide frame around a one-color interior, at least 3 wide on both axes. On such a box, repeating the line next to the far side gives the same grid as redrawing the frame. `$RepeatInnerSlice` is also defined on `striped-interior`.
- Non-concept cases that take `$AllInk & $StoredMarker` fail Subsumption by their `$MultiCellPiece` counterparts. Where `$AllInk` is defined, the non-marker ink is one solid rectangle of at least 3 cells, so it is the one piece of more than one cell. `$MultiCellPiece` is also defined on `stray-cell`.
- `$MultiCellPiece & $LoneMarker` fails Equivalence with `$AllInk & $LoneMarker`, and leaves because it takes one more non-concept branch. Under `$LoneMarker`, every non-marker ink cell has an ink neighbor, so every piece has more than one cell. A unique piece is then the same as connected ink.
- The concept base with `marker_color=RarestColor` or `background=DominantColor` fails Subsumption by the `$MultiCellPiece & $EachMarker & $CoverDiagonal & $RepeatInnerSlice` case that takes the same branch. Each `@derive` line has an `@ignore: derive concept` line that records this.
- `stray-cell` gets plausibility `borderline` and verdict `$MultiCellPiece`. A stray cell beside the box and the dot breaks the `background` scene claim, and a generator that put one there would most likely leave it in place.
- Witness resolutions:
    - `witness` reported that no run showed `$MultiCellPiece & $OneMarker` differing from `$AllInk & $EachMarker`. `stray-cell` resolves it.
    - It reported the same for `$StoredMarker & marker_color=RarestColor` against `$LoneMarker`. `touching-marker` resolves it.
    - It reported the same for `background=stored` against `background=DominantColor`. `big-box` resolves it.
    - It reported three `$OneMarker`/`$StraightOut` pairs. The Subsumption pruning above resolves them.
- `$RepeatInnerSlice` is undefined where a grown side has no slice that lies apart from the opposite side, as the Analyze report gives: the box is narrower than 3 along the stretch.
- Hints:
    - The `common-subexpr` hint on `line_src` led to merging its two clauses into one disjunction.
    - The `head-repeat` hint on `line_src` stays, under `@ignore`, because a line away from a grown side maps to itself in that relation.
    - The long-clause findings were wrapped.
- Deletions: the deletions that change nothing are guards that make the model undefined, which the pairs never trigger, or atoms that state the axis or direction a relation is keyed on. One deletion was taken: the stretched-box atom and the `inside` atom in the `$RepeatInnerSlice` fill, because `line_src` already limits the lines to the stretched box.
- The determination plan lists no actions: `background` is covered by DominantColor and `marker_color` by ChangedColor. So the solver has no Determine comp. The sweep gave only the stored values.
- Performance: every run finished in a few seconds.

## Open
- none

## Lib
- Isolated cell of a set, a cell with no 4-neighbor in the set. The solver-local form is `touching(P) :- ink(P), dir_elem(D), neighbor(P, D, Q), ink(Q).` with `marker($LoneMarker(), P) :- ink(P), !touching(P).`. The grep found the same shape in `3e980e27.dl` (`lone(K, P, Col) :- ink(K, P, Col), !joined(K, P).`).

## Fixes elsewhere
- none

## Tickets filed
- 10-367_task_b548a754_create.md
