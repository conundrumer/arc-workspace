# ecaa0ec1

## Concept
- Fits every pair: train0 BR→TL is a half turn, train1 TR→TL a quarter turn counterclockwise, train2 TL→BL counterclockwise, train3 TR→BR clockwise, and test0 BL→TR a half turn (`work/task/ecaa0ec1/check_concept.py`).
- The rotation is forced. The reflection that swaps the same two corners fails train0–train3. No single fixed turn fits: TR needs CCW in train1 and CW in train3.
- Every rule has a relational form: corners of the tile's box, diagonal and side offsets from a corner, and a C4 rotation about the box. Nothing approximates them.
- No witness has the verdict `other`.

## Choice points
- `marked-corner`
    - `concept`: the corner whose three marks all stand `mark-gap` out: on its diagonal, and in line with each of its two sides
    - `$TargetByDiagonal`: replaces `marks`. The marked corner is the one corner with a `marker` `mark-gap` out on its diagonal. Reads `mark-gap`. Undefined where no corner, or more than one, has such a marker. Fits every pair. Witness `single-diagonal-mark`: only the diagonal mark is present, so it breaks `marks`. Plausibility `variant`: a variant marks the target with one cell. It breaks the invariant that each input has three marks at the marked corner. Verdict `$TargetByDiagonal`.
    - `$TargetBySideMarks`: replaces `marks`. The marked corner is the one corner with markers `mark-gap` out in line with both of its sides. A diagonal mark is not needed. Reads `mark-gap`. Undefined where no corner, or more than one, has them. Fits every pair. Witness `side-marks-only`: breaks `marks`. Plausibility `variant`. It breaks the same three-marks invariant. Verdict `$TargetBySideMarks`.
    - `$TargetByQuadrant`: replaces `marks`. The marked corner is the corner whose quadrant holds every marker but the pointer. A corner's quadrant is the cells on that corner's side of the tile, or in line with the corner, on both axes. Reads no `mark-gap`. Undefined where the other markers span two quadrants, or one lies in no quadrant. Fits every pair. Witness `marks-three-out`: the marks stand three out, so it breaks `marks` at `mark-gap` 2. Plausibility `variant`: the mark distance changes in a variant. It breaks the invariant that the marks stand two out. Verdict `$TargetByQuadrant`.
- `pointer`
    - `concept`: the `marker` `pointer-gap` out on a corner's diagonal. Its corner is that corner.
    - `$PointerByQuadrant`: replaces `pointer`. The pointer is the one marker outside the marked corner's quadrant, and its corner is the quadrant it lies in. Reads no `pointer-gap`. Undefined where no marker, or more than one, lies outside that quadrant, or a marker lies in no quadrant. Fits every pair. Witness `pointer-two-out`: the pointer stands two out on the BR diagonal, so it breaks `pointer` at `pointer-gap` 1. Plausibility `variant`. It breaks the invariant that the pointer touches its corner. Verdict `$PointerByQuadrant`: the pointer turns with the tile and lands two out from TL.
        - `pointer-placement`
            - `concept`: the pointer turns with the tile about its center
            - `$PointerSnapsToDiagonal`: replaces `turn-pointer`. The pointer is drawn `pointer-gap` out on the marked corner's diagonal, wherever it stood. Reads `pointer-gap`. Fits every pair. Witness `pointer-two-out`. Plausibility `variant`. It breaks the invariant that the pointer touches its corner. Verdict `$PointerByQuadrant`, not this branch.
- `turn`
    - `concept`: the C4 rotation that takes the pointer's corner to the marked corner
    - `$Reflect`: replaces `turn-tile`. The D4 reflection that swaps the two corners: the side flip for adjacent corners, the diagonal flip for opposite ones. Fails Fit at train0. The anti-diagonal flip gives `8 8 1` as row 5, cols 4–6, where the output has `8 1 1`.
- `marks`
    - `concept`: the three marks become background
    - `$KeepMarks`: replaces `wipe-marks`. Every marker but the pointer stays. Fails Fit at train0: the output has `0` at (3,2), (3,4) and (5,2).
- `tile-cells`
    - `concept`: the tile is every cell that is neither `background` nor `marker`
    - `tile_color=stored`: replaces `tile`. The tile is the cells of the stored colors 1 and 8. Every other cell outside the turned tile and the pointer becomes background. Undefined where no cell has a stored color, or the stored-color cells do not span a square. Fits every pair. Witness `tile_color=stored`: a 2 at the tile's top middle breaks `tile`, whose `tile-colors` are 1 and 8. Plausibility `variant`: the tile has a third color. It breaks the invariant that the tile has only the colors 1 and 8. Verdict `concept`: the 2 turns with the tile.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: the background is the commonest color of the input. Undefined where the top count ties. Fits every pair. Witness `background=DominantColor`: the same scene on a field of 5. At the stored background 0 the concept takes the field as tile and is undefined. Plausibility `variant`: it is a color permutation. It breaks the invariant that the background is 0. Verdict `background=DominantColor`.
- `marker`
    - `concept`: stored, 4
    - `marker=RarestColor`: Fails Fit at train0, whose input ties 1 and 4 at four cells each. Train1 gives 8 alone.
    - `marker=SharedColor`: Fails Fit at train0, where it gives every color of the input: 0, 1, 4 and 8.
- `marked-corner` & `turn`, `marked-corner` & `marks`, `marked-corner` & `tile-cells`, `marked-corner` & `background`, `marked-corner` & `marker`, `pointer` & `turn`, `pointer` & `marks`, `pointer` & `tile-cells`, `pointer` & `background`, `pointer` & `marker`, `pointer-placement` & `turn`, `pointer-placement` & `marks`, `pointer-placement` & `tile-cells`, `pointer-placement` & `background`, `pointer-placement` & `marker`, `turn` & `marks`, `turn` & `tile-cells`, `turn` & `background`, `turn` & `marker`, `marks` & `tile-cells`, `marks` & `background`, `marks` & `marker`, `tile-cells` & `background`, `tile-cells` & `marker`, `background` & `marker`: the two branches' changes applied together
- `marked-corner` & `pointer`, `marked-corner` & `pointer-placement`: the two branches' changes applied together. With `$TargetByDiagonal` or `$TargetBySideMarks`, the pointer is the one marker outside that corner's quadrant.
    - `$TargetByQuadrant` & `$PointerByQuadrant`: each branch reads the other's result, so they are defined together. The pointer is the one marker alone in its quadrant, and the marked corner is the quadrant that holds every other marker. Undefined where no marker, or more than one, is alone in its quadrant, or a marker lies in no quadrant.
    - `$TargetByQuadrant` & `$PointerSnapsToDiagonal`: the same joint definition, with the pointer drawn `pointer-gap` out on the marked corner's diagonal.

## Open parameters
- none

## Not formed
- The marked corner as the corner nearest the marks' centroid: it has no relational form.
- `background=SharedColor`, `background=RarestColor`: on train0's input they give {0, 1, 4, 8} and {1, 4}, never 0 alone, so they fail Fit at train0 the way the `marker` derivations do.
- A fixed turn (always CW, CCW or a half turn): the pairs use all three, and TR goes CCW in train1 and CW in train3.
- The tile as the 8-connected component of non-background cells: the pointer touches a corner diagonally and would join the tile. It would be undefined on every pair.
- The pointer moved onto the diagonal mark's cell, two out: fails train0, whose output has the 4 at (4,3), not at (3,2).
- A swap of the tile's two colors: every output keeps each tile cell's color, only moved.

## Tickets filed
- none
