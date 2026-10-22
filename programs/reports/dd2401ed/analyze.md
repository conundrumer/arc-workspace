# dd2401ed

## Concept
- The concept fits every pair, and each claim has a relational form. No witness has the verdict `other`, and the rule as the generator applies it is the rule `move-divider` with `recolor-swept` as the concept file states it.
- The concept is undefined where the destination, at index 2(k+1)−1 from `near_edge`, falls outside the grid. This includes every input whose divider stands in the far half, and so every mirrored input at the stored `near_edge`.
- The inputs hold no far mark on the destination column (`destination-clear`). With the far marks placed at random, the chance of this on all five inputs is about 1%, so the generator likely keeps that column clear.

## Choice points
- `near-edge`
    - `concept`: `near_edge` stored as left
    - `$NearEdgeNearer`: replaces the stored `near_edge` with the edge the divider is nearer to; undefined where the divider stands on the center line, or where no single full line exists. It fits every pair. Witness `near-marks-on-right` (train0 input mirrored left to right) breaks `near-marks`, `far-marks` and `room-to-move` at the stored assignment, plausibility `variant`, verdict `$NearEdgeNearer`. It breaks the invariant that the divider stands in the left half with the near marks to its left.
    - `$NearEdgeOfNearMarks`: replaces the stored `near_edge` with the side of the divider that holds every `near_color` cell; undefined where `near_color` cells stand on both sides or nowhere. It fits every pair. Witness `near-marks-on-right-wide` (train1 input mirrored) breaks `near-marks`, `far-marks` and `room-to-move`, plausibility `variant`, verdict `$NearEdgeOfNearMarks`, and breaks the same invariant. It fails Subsumption: where it is defined and the destination lies inside the grid, the divider stands nearer to that side, so `$NearEdgeNearer` gives the same output, and `$NearEdgeNearer` is also defined on inputs with no near mark.
- `line-color`
    - `concept`: `line_color` stored as 5
    - `$LineColorOfFullLine`: replaces the stored `line_color` with the color of the one full line of a non-`background` color; undefined where no such line or more than one exists. It fits every pair. Witness `divider-of-another-color` (train0 input with the divider in 3) breaks `divider-line`, plausibility `variant`, verdict `$LineColorOfFullLine`. It breaks the invariant that the divider is 5.
- `near-color`
    - `concept`: `near_color` stored as 1
    - `near_color=RarestColor`: the color with the fewest cells in the input, a value for each tie. It fits every pair. Witness `near_color=RarestColor` (train0 input with four near marks and three far marks) breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$NearColorOfNearSide`: replaces the stored `near_color` with the one non-`background` color on the near side of the divider; undefined where that side holds no such color or more than one. It fits every pair. Witness `near-marks-of-another-color` (train0 input with the near marks in 3) breaks `background`, plausibility `variant`, verdict `$NearColorOfNearSide`. It breaks the invariant that the near marks are 1.
- `background`
    - `concept`: `background` stored as 0
    - `background=DominantColor`: the color with the most cells in the input. It fits every pair. Witness `background=DominantColor` (train0 input with the background in 4) breaks `background`, plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that the background is 0.
- `destination-content`
    - `concept`: every cell of the destination line takes `line_color`
    - `$MarkOverLine`: replaces `move-divider` on the destination line: a non-`background` cell there keeps its input color. It fits every pair. Witness `far-mark-on-destination` (train0 input with a far mark at (2,9)) breaks `destination-clear`, plausibility `borderline`, verdict `concept`. It breaks the invariant that no far mark stands on the destination column.
    - `$SweptMarkOverLine`: replaces `move-divider` and `recolor-swept` on the destination line: the sweep takes in the destination, so a far mark there takes `near_color`. It fits every pair. Witness `far-mark-on-destination-swept` (train0 input with a far mark at (5,9)) breaks `destination-clear`, plausibility `borderline`, verdict `concept`, and breaks the same invariant.
- `recolored-colors`
    - `concept`: only `far_color` cells are recolored
        - `far-color`
            - `concept`: `far_color` stored as 2
            - `$FarColorOfFarSide`: replaces the stored `far_color` with the one non-`background` color on the far side of the divider; undefined where that side holds no such color or more than one. It fits every pair. Witness `far-marks-of-another-color` (train0 input with the far marks in 3) breaks `background`, plausibility `variant`, verdict `$FarColorOfFarSide`. It breaks the invariant that the far marks are 2. It fails Subsumption: where it is defined, the swept columns hold only that color and `background`, so `$RecolorAnySwept` gives the same output, and `$RecolorAnySwept` is also defined where the far side holds two mark colors.
    - `$RecolorAnySwept`: replaces `recolor-swept`: every cell between the old and the new line that is neither `background` nor `line_color` takes `near_color`; it reads no `far_color`. It fits every pair. Witness `mark-of-third-color-swept` (train0 input with a 3 at (2,7)) breaks `background`, plausibility `foreign`, verdict `concept`. It breaks the invariant that the inputs hold only the colors 0, 1, 2 and 5.
- `recolored-region`
    - `concept`: the columns strictly between the old and the new line
    - `$RecolorNearSide`: replaces `recolor-swept`: every `far_color` cell on the near side of the destination, the old line excepted, takes `near_color`. It fits every pair. Witness `far-mark-on-near-side` (train0 input with a far mark at (3,1)) breaks `far-marks`, plausibility `foreign`, verdict `$RecolorNearSide`. It breaks the invariant that every far mark stands on the far side of the divider.
- `destination-index`
    - `concept`: the count of lines from `near_edge` up to and including the divider doubles, index 2(k+1)−1
    - `$DoubleNearWidth`: replaces `move-divider`: the count of lines between `near_edge` and the divider doubles, index 2k. It fails Fit at train0 (the destination is column 8, and the output has the line at column 9), and at every other pair.
- `near-edge` & `line-color`, `near-edge` & `far-color`, `near-edge` & `background`, `near-edge` & `destination-content`, `near-edge` & `recolored-colors`, `near-edge` & `recolored-region`, `near-edge` & `destination-index`, `line-color` & `near-color`, `line-color` & `far-color`, `line-color` & `background`, `line-color` & `destination-content`, `line-color` & `recolored-colors`, `line-color` & `recolored-region`, `line-color` & `destination-index`, `near-color` & `far-color`, `near-color` & `background`, `near-color` & `destination-content`, `near-color` & `recolored-colors`, `near-color` & `recolored-region`, `near-color` & `destination-index`, `far-color` & `background`, `far-color` & `destination-content`, `far-color` & `recolored-region`, `far-color` & `destination-index`, `background` & `destination-content`, `background` & `recolored-colors`, `background` & `recolored-region`, `background` & `destination-index`, `destination-content` & `recolored-colors`, `destination-content` & `recolored-region`, `destination-content` & `destination-index`, `recolored-colors` & `recolored-region`, `recolored-colors` & `destination-index`, `recolored-region` & `destination-index`: the two branches' changes applied together
- `near-edge` & `near-color`: the two branches' changes applied together
    - `$NearEdgeOfNearMarks` & `$NearColorOfNearSide`: each of the two derivations reads the other's value, so the model takes each pair of a side and a color in which the color is the one mark color on that side and every cell of it stands on that side. On each train input, two pairs meet this: the near side with 1, and the far side with 2. The reading from the far side puts the destination outside the grid, so the model is undefined there.

## Open parameters
- none

## Not formed
- A destination read from the far marks, such as the column before the nearest far mark that stays: train3 moves the divider to column 7, and the nearest far mark that stays is at column 9.
- A fixed shift of the divider: the shifts in train0–train3 are 5, 6, 2 and 4.
- A copy of the near region into the vacated columns: train0 output columns 5–8 hold the swept far marks, not a copy of columns 0–3.
- A divider clamped to the far edge where the destination falls outside the grid: no pair and no source gives an output for that input.
- A `factor` derived from the input: no proposer and no clause reads a multiple from an input alone, and the pairs give 2.
- `line_color`, `far_color` or `background` by `RarestColor`: the rarest color is 1 in every train input, so each fails Fit at train0.
- `line_color`, `near_color` or `far_color` by `DominantColor`: the commonest color is 0 in every input, so each fails Fit at train0.
- Any color by `SharedColor`: on one input it gives every color of that input, so the model gives more than one output at train0 and fails Fit.
- Color derivations by the proposers that read `ex_out`: with `ex_out` empty on an input they give no value, and the model is undefined at every pair.

## Tickets filed
- 10-858_task_dd2401ed_analyze.md
