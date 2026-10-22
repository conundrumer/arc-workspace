# c074846d

## Concept
- The concept case fits every pair at its stored assignment (`probe.py` over the pairs). Its rule reads each arm cell by its cardinal direction and distance from the pivot, and it turns each arm cell about every pivot cell on the same row or column. It is total on every input.
- No witness has verdict `other`. Where an input breaks `room-to-turn`, the rule drops the cells that would fall off the grid. The generator does not produce such an input, and a person reads the clipped output, so the verdict there is `concept`.
- On `two-sticks` (verdict `$PerStick`), `bent-arm` (verdict `$RotateOffsets`) and `corner-touch` (verdict `$RotateOffsets & $PerStick`), the concept case's output is not the one the generator would give.

## Choice points
- `turn-geometry`
    - `concept`: each arm cell at distance k from the pivot in a cardinal direction d goes to distance k in the direction `sense` turns d to. An arm cell off the pivot's row and column keeps its color.
    - `$RotateOffsets`: replaces `swing`. Each arm cell's offset from the pivot turns a quarter turn in `sense`, and every arm cell moves and leaves trail, wherever it lies. Parameters as the concept. Defined on every input. Fits every pair. Witness `bent-arm`: breaks `arm`, at the stored assignment, `borderline`, verdict `$RotateOffsets`. It breaks the invariant that every input's arm cells lie in one straight run from the pivot.
    - `$Reflect`: replaces `swing`. The arm is mirrored across a stored diagonal axis through the pivot, in place of `sense`. Defined on every input. Fails Fit: train2 under the main diagonal, and train0 under the anti-diagonal.
- `stick-scope`
    - `concept`: one pivot set. Each arm cell turns about every pivot cell (`pivot` states one).
    - `$PerStick`: replaces `pivot` and `swing`. Each 4-connected component of non-background cells is a stick, and its arm cells turn only about the pivot cells of the same component. Parameters as the concept. Defined on every input. Fits every pair. Witness `two-sticks`: breaks `pivot`, at the stored assignment, `variant`, verdict `$PerStick`. It breaks the invariant that every input holds one pivot cell.
        - `stick-adjacency`
            - `concept`: 4-adjacency joins the cells of a stick.
            - `$CornerJoin`: 8-adjacency joins the cells of a stick, so sticks that touch only at a corner are one stick. Defined on every input. Fits every pair. Witness `corner-touch`: breaks `pivot` and `arm`, at the stored assignment, `foreign`, verdict `$RotateOffsets & $PerStick`. It breaks the invariants that every input holds one pivot cell and that the arm is one straight run.
- `new-arm-extent`
    - `concept`: the turned arm has the input arm's length.
    - `$CastToEdge`: replaces `swing`. The turned arm runs from the pivot to the grid edge. Defined on every input. Fails Fit: train2.
- `trail-extent`
    - `concept`: the cells the arm held take `trail_color`.
    - `$SweepTrail`: replaces `trail`. Every cell the arm sweeps through in the quarter turn takes `trail_color`. Defined on every input. Fails Fit: train0.
- `pivot_color`
    - `concept`: stored, 5.
    - `pivot_color=RarestColor`: the pivot colors are the input's rarest colors, ties included. Replaces the stored `pivot_color`. Defined on every input. Fits every pair: on train2 and train3, the derivation gives 2 and 5, and a 2 cell as a pivot has no other arm cell in line. Witness `pivot_color=RarestColor`: breaks `blank-field`, at the stored assignment, `borderline`, verdict `concept`. It breaks the invariant that every input holds only the background, pivot and arm colors.
    - `pivot_color=DominantColor`, `pivot_color=SharedColor`: each makes background cells pivots. Fails Fit: train0.
- `arm_color`
    - `concept`: stored, 2.
    - each proposer derivation (`RarestColor`, `DominantColor`, `SharedColor`, and the ones that read `ex_out`, which give no value): fails Fit: train0.
- `trail_color`
    - `concept`: stored, 3.
    - each proposer derivation (`RarestColor`, `DominantColor`, `SharedColor`, and the ones that read `ex_out`, which give no value): fails Fit: train0.
- `turn-geometry` & `stick-scope`, `turn-geometry` & `pivot_color`, `stick-scope` & `pivot_color`, `new-arm-extent` & `trail-extent`, `new-arm-extent` & `stick-scope`, `new-arm-extent` & `pivot_color`, `trail-extent` & `stick-scope`, `trail-extent` & `pivot_color`: the two branches' changes applied together. `$RotateOffsets & $PerStick` turns each stick's offsets about its own pivot. `$PerStick & pivot_color=RarestColor` puts a stray rarest-color cell in a component of its own, where no arm cell turns about it.
- `turn-geometry` & `new-arm-extent`, `turn-geometry` & `trail-extent`: `$CastToEdge` and `$SweepTrail` read the arm cell's cardinal direction, and `$RotateOffsets` moves cells that have none. Each case that takes `$CastToEdge` or `$SweepTrail` fails Fit at the pair its branch fails, whatever reading it gives those cells, so no case takes either combination.
- `turn-geometry` & `stick-adjacency`: `$RotateOffsets & $PerStick & $CornerJoin` turns the offsets of each 8-connected stick about its own pivots. These are the two branches' changes applied together.

## Open parameters
- none

## Not formed
- The arm turns toward the side with the most room, or toward the nearest edge: train0 turns up, where the room up (2) equals the room down and is less than the room on the right (3), so no reading of room picks the turn.
- `sense` derived: no proposer and no feature of an input gives a turn sense, and the pairs fix clockwise.
- A different trail or arm color for the turned arm: every pair paints the turned arm in `arm_color` and the left cells in `trail_color`.

## Tickets filed
- none
