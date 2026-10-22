# d282b262

## Concept
- Fits every pair at `heading` R and `bg` 0. The lib component `Gravity`, over the 4-connected components of the non-`bg` cells, gives each train and test output exactly. No witness has the verdict `other`. The `slide` rule is the generator's rule as it stands, and it has a relational form.

## Choice points
- `motion`: whether each object moves on its own or all the content moves as one
    - `concept`: each object travels its own distance
        - `stop`: what stops an object
            - `concept`: the frame edge, or a cell of another object at that object's resting place, straight ahead
            - `$StaticObstacles`: replaces `slide`; an object stops at the frame edge or against another object at its input place; defined on every input; fails Fit at train0 (the 2/1 object stops at cols 5–7 against the 1/4 object's input place, and the output has it at cols 9–11)
            - `$CornerContact`: replaces `slide`; an object also stops when one of its cells touches a cell of a settled object at a corner; defined on every input; fails Fit at test0 (the 1/7 object stops at cols 10–11, touching the settled 8/4 object at (12,12), and the output has it at cols 13–14)
        - `unit`: what moves as one piece
            - `concept`: an object
                - `adjacency`: which cells join into one object
                    - `concept`: 4-adjacency
                    - `$Diagonal8Bodies`: replaces `objects`; cells that touch at a corner also join; defined on every input; fits every pair; witness `corner-touch`: breaks `apart`, stored assignment, plausibility `variant`, verdict `concept`; breaks the invariant that every object has background on all eight sides
                - `footprint`: which cells of an object block other objects
                    - `concept`: the object's own cells
                    - `$BoxBodies`: replaces `slide`; each cell of an object's bounding box blocks; undefined on an input where an object's box covers a cell of another object; fits every pair; witness `notch`: breaks no scene claim, stored assignment, plausibility `variant`, verdict `concept`; breaks the invariant that every object fills its bounding box (each object is a full square two-color checkerboard)
            - `$CellBodies`: replaces `objects`; each non-`bg` cell moves as a piece of its own; defined on every input; fails Fit at train0 (row 5 of the 2/1 object packs to cols 12–14, and the output has it at cols 9–11)
    - `$SharedShift`: replaces `slide`; all non-`bg` content shifts by one offset, the least that brings a cell to the right edge; defined on every input; fails Fit at train0 (the 8/3 object lands at cols 5–7, and the output has it at cols 12–14)
- `bg`: where the background color comes from
    - `concept`: stored, 0
    - `bg=DominantColor`: `bg` derived as the commonest color of the input; replaces `objects`; defined on every input; fits every pair; witness `bg=DominantColor`: breaks no scene claim, stored assignment, plausibility `borderline`, verdict `concept`; breaks the invariant that the background is the commonest color of each input (the largest object in the evidence is 5×5)
- `bg` & `motion`, `bg` & `stop`, `bg` & `unit`, `bg` & `adjacency`, `bg` & `footprint`, `stop` & `unit`, `stop` & `adjacency`, `stop` & `footprint`, `adjacency` & `footprint`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A derived `heading`: nothing in an input points to a side, and every pair slides to the right, so no derivation from the inputs gives the value.
- An object as one two-color checkerboard, so that two checkerboards that touch move as separate pieces: the split of a touching group into checkerboards is not unique (two side-by-side 2×2 checkerboards of 1 and 2 with matching parity also form one 2×4 checkerboard), so the claim has no relational form.

## Tickets filed
- 10-655_task_d282b262_analyze.md
