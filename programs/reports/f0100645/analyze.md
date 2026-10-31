# f0100645

## Concept
- Fits train0, train1 and test0. Checked by `work/task/f0100645/check_concept.py` and `work/task/f0100645/probe.py`. Both restate Components8 and Gravity in Python, because no souffle binary is installed (see `progress-analyze.md`).
- No witness has the verdict `other`. Each rule has a relational form: the walls are uniform opposite edge lines, the bodies are 8-connected components of one wall color, and the slide is Gravity per heading with the wall line as blocked cells.
- The concept is undefined where shapes of the two colors land on one cell. That happens only on inputs where the two colors' paths cross, which is the `opposite-colors` point.
- Every input meets one invariant that the concept's Scene does not state: no cell of the other wall color lies between a shape cell and its own wall along its line (probe `invariant`, empty on all three inputs). `opposite-cross` breaks this invariant, and its verdict is `$CollideOpposite`, against the concept, at `borderline`.

## Choice points
- `rigid-body`: what moves as one rigid body
    - `concept`: each 8-connected component of one wall color
    - `$FourConnected`: replaces `shapes` with 4-connected components, no parameters, defined where the concept is. Fails Fit at train1: the 9 cell (2,4) touches its shape only at a corner, so it slides alone and stops at (2,2) where the output has it at (2,3).
    - `$WholeColorBody`: replaces `shapes` and `fall-to-own-wall` with all cells of one color moving as one body, no parameters, defined where the concept is. Fails Fit at train0, where the 4 shapes shift by 2, 3 and 1.
    - `$PerCellFall`: replaces `fall-to-own-wall` with each cell sliding alone, no parameters, defined where the concept is. Fails Fit at train0: row 0's 4 cell lands at (0,1), where the output has (0,2).
- `travel`: how far a body travels
    - `concept`: until it makes contact (`stack`)
        - `stacking`: whether a stopped body of the same heading stops a later one
            - `concept`: it does (`stack`)
            - `$NoStacking`: replaces `stack` so that a body stops only against its own wall, no parameters, undefined where two same-color bodies land on one cell. Fails Fit at train1: the 8 cell (7,2) reaches (7,7), where the output has (7,5).
        - `opposite-colors`: what a body of the other color does to a sliding body
            - `concept`: nothing; the two pass through each other
            - `$CollideOpposite`: adds a rule that bodies move one cell per step together and a body also stops against a body of the other color. No parameters, defined where the concept is and also where the concept's landings overlap. Fits every pair. Witness `opposite-cross`: it breaks no scene claim, its plausibility is `borderline`, and its verdict is `$CollideOpposite`. The invariant it breaks: no cell of the other wall color lies between a shape cell and its wall along its line.
    - `$FixedShift`: replaces `stack` with a stored shift `k` that every body travels, undefined where a body would leave the grid. Fails Fit at train0 at every `k` from 0 to 9: the shifts there are 1 to 4.
- `heading`: where each color's heading comes from
    - `concept`: derived from the walls. The wall axis is the axis whose two edge lines are uniform and of different colors, and each color heads toward the wall of that color.
    - `$StoredHeading`: replaces `fall-to-own-wall` with a stored color-to-direction table read from the train pairs (4 L, 6 R, 9 L, 8 R), undefined where a color has no entry. Fails Fit at test0: 8 heads R in the table but the test's 8 wall is on the left, and 1 has no entry.
    - `$StoredAxis`: replaces the derived axis of `two-walls` with a stored axis `H`, the side still derived from the wall color, undefined where the edges on that axis are not two uniform lines of different colors. Fits every pair, and fails Subsumption: only one axis can hold a wall pair, so wherever this model is defined it gives the concept's output. Witness `$StoredAxis`: train0 transposed. It breaks no scene claim, its plausibility is `variant`, its verdict is `concept`, and the branch is undefined on it. The invariant it breaks: the walls are on the left and right edges. No witness exists on which this branch is defined.
- `stray-cells`: what a cell does whose color is neither the background nor a wall color
    - `concept`: it becomes background (`keep-rest`)
    - `$StrayStays`: replaces `keep-rest` so that such cells keep their place and their color, and a body can pass over them. No parameters, defined where the concept is. Fits every pair. Witness `stray-color-cell`: it breaks `shapes`, its plausibility is `borderline`, and its verdict is `$StrayBlocks`. The invariant it breaks: every input holds only the background and the two wall colors.
        - `stray-blocking`: whether a kept stray cell stops a body
            - `concept`: it does not (`$StrayStays`)
            - `$StrayBlocks`: adds stray cells to the blocked cells of `stack`, no parameters, defined where the concept is. Fits every pair. Witness `stray-color-cell`: it breaks `shapes`, its plausibility is `borderline`, and its verdict is `$StrayBlocks`. The invariant it breaks: every input holds only the background and the two wall colors.
- `background`: the fill color
    - `concept`: stored `background` = 7
    - `background=DominantColor`: derives `background` as the commonest color of the input in place of the stored value, defined where the concept is. Fits every pair, since 7 is the commonest color of every input. Witness `background=DominantColor`: train0 with background 0. It breaks `background`, its plausibility is `variant`, and its verdict is `background=DominantColor`. The invariant it breaks: the background is 7 in every input.
- `rigid-body` & `travel`, `rigid-body` & `heading`, `rigid-body` & `stray-cells`, `rigid-body` & `background`, `rigid-body` & `opposite-colors`, `rigid-body` & `stray-blocking`, `travel` & `heading`, `travel` & `stray-cells`, `travel` & `background`, `heading` & `stray-cells`, `heading` & `background`, `heading` & `stacking`, `heading` & `opposite-colors`, `heading` & `stray-blocking`, `stray-cells` & `background`, `stray-cells` & `stacking`, `stray-cells` & `opposite-colors`, `background` & `stacking`, `background` & `opposite-colors`, `background` & `stray-blocking`, `stacking` & `opposite-colors`, `stacking` & `stray-blocking`, `opposite-colors` & `stray-blocking`: the two branches' changes applied together
- `rigid-body` & `stacking`: the two branches' changes applied together, apart from the line below
    - `$WholeColorBody` & `$NoStacking`: `$WholeColorBody`'s model alone. One body per heading leaves nothing to stack against, so `stacking` exists only with the component and per-cell bodies together with contact travel, and it stands under `travel`'s concept branch.
- `travel` & `stray-blocking`: the two branches' changes applied together, apart from the line below
    - `$FixedShift` & `$StrayBlocks`: the model of `$FixedShift` & `$StrayStays`, since a fixed shift makes no contact

## Open parameters
none

## Not formed
- A stored color priority for shapes of the two colors that land on one cell: such a landing arises only on inputs where paths cross, which the `opposite-colors` point covers. A priority between task colors has no reading a person would take.
- A stored pair of wall colors: train0 (4, 6) and train1 (9, 8) differ, so no stored pair fits both. A stored color-to-heading table is `$StoredHeading`.
- Shapes that touch their own wall as part of the wall: such a shape does not move under either reading, so no input separates them.
- Order of resting among same-heading bodies: the resting places of rigid bodies falling together do not depend on the order, so no input separates the orders.

## Tickets filed
- none
