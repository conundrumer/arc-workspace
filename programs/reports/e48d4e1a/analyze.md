# e48d4e1a

## Concept
- The concept fits every train pair and the test pair. No witness has the verdict `other`, so no witness stands against the concept case.

## Choice points
- `shift-direction`
    - `concept`: `shift_dir` is stored as bottom-left.
    - `$ShiftFromMarkCorner`: replaces `shift-cross`. The cross moves toward the corner diagonally opposite the corner that holds a `mark_color` cell. Reads no `shift_dir`. Undefined where no corner, or more than one corner, holds a `mark_color` cell. Fits every pair. Witness `marks-top-left` breaks `mark-stack` (`mark_corner`). It stands at the stored assignment, plausibility `borderline`, verdict `$ShiftFromMarkCorner`. Invariant broken: in every input, the marks run down the right edge from the top-right corner.
- `mark-color`
    - `concept`: `mark_color` is stored as `5`.
    - `mark_color=RarestColor`: derives `mark_color` as the rarest color of the input, ties included. Replaces the stored value in `mark-stack` and `count-marks`. Undefined nowhere. Fits every pair. Witness `mark_color=RarestColor` breaks `mark-stack` (the marks are not `mark_color`). It stands at the stored assignment, plausibility `variant`, verdict `mark_color=RarestColor`. Invariant broken: in every input, the marks are `5`.
    - `mark_color=VanishedColor`: on one input with `ex_out` empty, derives every color of that input. Fails Fit at train0, because it counts every cell.
    - `mark_color=SharedColor`: on one input, derives every color of that input. Fails Fit at train0, for the same reason.
- `background`
    - `concept`: `bg` is stored as `0`.
    - `bg=DominantColor`: derives `bg` as the commonest color of the input. Replaces the stored value in `full-cross` and `erase-marks`. Undefined nowhere. Fits every pair. Witness `bg=DominantColor` breaks `full-cross` (the field is not `bg`). It stands at the stored assignment, plausibility `variant`, verdict `bg=DominantColor`. Invariant broken: in every input, the field is `0`.
    - `bg=SharedColor`: on one input, derives every color of that input. Fails Fit at train0, because no one background exists.
- `mark-count`
    - `concept`: the shift is the number of `mark_color` cells.
    - `$CountMarkRun`: replaces `count-marks`. The shift is the length of the unbroken run of `mark_color` cells down `mark_edge` from `mark_corner`, so it reads `mark_corner` and `mark_edge`. Undefined nowhere. Fits every pair. Witness `gapped-marks` breaks `mark-stack` (the marks do not form one run). It stands at the stored assignment, plausibility `borderline`, verdict `concept`. Invariant broken: in every input, the marks form one run from the corner.
- `off-frame`
    - `concept`: a moved line that passes the frame edge is dropped, and the output keeps the other line.
        - `line-motion`
            - `concept`: each moved line is drawn again edge to edge.
            - `$TranslateCross`: replaces `shift-cross`. The cross moves as one object. Cells that it moves past the edge are lost, and the cells that it leaves become `bg`. Fails Fit at train0: output (0,1), (1,1), (8,8) and (8,9) are `2`, and the translated cross leaves them `0`.
    - `$WrapShift`: replaces `shift-cross`. A moved line that passes an edge comes back at the opposite edge, with each index taken modulo the grid extent. Undefined nowhere. Fits every pair. Witness `shift-past-edge` breaks no scene claim. It stands at the stored assignment, plausibility `borderline`, verdict `concept`. Invariant broken: in every input, the moved cross stays inside the frame.
    - `$RefusePastEdge`: replaces `shift-cross`. Undefined where a moved line passes the frame edge, and gives the concept's output elsewhere. Fits every pair. It has no witness on which it is defined: wherever it is defined, it gives the concept's output, so the concept subsumes it and it fails Subsumption. Witness `shift-past-edge`, on which it is undefined, has verdict `concept`.
- `shift-direction` & `mark-color`, `shift-direction` & `background`, `shift-direction` & `mark-count`, `shift-direction` & `off-frame`, `mark-color` & `background`, `mark-color` & `mark-count`, `mark-color` & `off-frame`, `background` & `mark-count`, `background` & `off-frame`, `mark-count` & `off-frame`: the two branches' changes applied together
- `line-motion` & `off-frame`: `$TranslateCross` & `$WrapShift` gives the model of `$WrapShift` alone, because a cyclic translation of full lines draws full lines. So `line-motion` stands under the concept branch of `off-frame`. `$TranslateCross` & `$RefusePastEdge` gives `$TranslateCross`'s output where no line passes the edge, and is undefined elsewhere.

## Open parameters
- none

## Not formed
- A separate shift amount for each axis: in every pair, both axes move by the mark count. No source gives a reading in which the two amounts differ.
- The cross color as a parameter: that color changes from pair to pair, and the program reads it from the full lines of the input.
- Keeping the marks in the output: every output erases them, and no reading of the pairs keeps them.
- The shift as the row extent of the marks: under `mark-stack` it equals the count, and it parts from `$CountMarkRun` only on gapped marks. No source suggests it.

## Tickets filed
- none
