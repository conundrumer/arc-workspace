# c909285e

## Concept
- Fits every pair: in each input, exactly one color's cells form a rectangle outline, and the crop of its box, outline included, is the output.
- The rule `crop-outline` has a relational form, so no part of it is an approximation.
- No witness has the verdict `other`.
- The inputs are plaids: a cell's color is fixed by the kind of its row and the kind of its column. That is the reading of the scene claim `patterned-field`; the concept's program does not read it.
- The outline is 7 by 7 in the train pairs and 6 by 6 in the test, and it never touches the grid edge.

## Choice points
- `box-source`: which cells give the box that is cropped
    - `concept`: the one color whose cells are exactly a rectangle outline; undefined where no color, or more than one, is.
    - `$RarestColor`: replaces `one-outline` and `outline-color-unique` with "the box is the bounding box of the color that covers the fewest cells"; undefined where two colors tie for fewest. Fits every pair. Witness `sparse-color`: ordinary, verdict `concept`. It breaks no scene claim. The plaid uses 8 in one row and no column, so 8 covers 12 cells and the outline covers 24.
    - `$PatternBreak`: replaces `outline-color-unique` with "the box is the bounding box of the cells that break the plaid"; undefined where no cell breaks it. Fits every pair. Fails Relational form: recovering a plaid from a grid with an unknown set of overwritten cells means finding the fewest cells whose change makes the grid a product of row kinds and column kinds, and that has no relational form. The probe used an approximation of it: two rows, or two columns, are alike when they agree at more than two thirds of their cells. That approximation is also undefined on `wide-outline`. Witness `pattern-color-outline`: variant, verdict `$PatternBreak`. It breaks `outline-color-unique` and the invariant "the outline's color appears nowhere else in the input". The square is drawn in 4, which the plaid also uses.
    - `$OneBodyColor`: replaces `one-outline` with "the box is the bounding box of the one color whose cells form one 8-connected body"; undefined where no color does, or more than one does. Fits every pair. Witness `outline-with-tick`: borderline, verdict `$OneBodyColor`. It breaks `one-outline` and the invariant "the outline color's cells are exactly a rectangle outline". One more outline-color cell sits inside the square, so the concept is undefined there.
        - `adjacency`
            - `concept`: 8-adjacency.
            - `$EdgeContact`: the body is joined by 4-adjacency; undefined as `$OneBodyColor` is. Fits every pair. Witness `shifted-outline`: ordinary, verdict `concept`. It breaks no scene claim. A 6 by 6 outline at rows 5–10, cols 11–16 leaves the lines of 5 joined only at corners, so 5 is a second one-body color under 8-adjacency.
    - `$InteriorColor`: replaces `one-outline` with "the box is the bounding box of the one color that no edge cell holds"; undefined where no color, or more than one, keeps off the edge. Fits every pair. Witness `outline-with-tick`: borderline, verdict `$InteriorColor`. It breaks `one-outline` and the invariant "the outline color's cells are exactly a rectangle outline".
- `box-shape`: which boxes the model accepts
    - `concept`: any rectangle.
    - `$SquareBox`: adds "the box is a square"; undefined where the box is not a square. Fits every pair. Fails Subsumption: wherever it is defined, its output is the concept's. No witness exists on which it is defined and differs from the concept. Witness `wide-outline`: variant, verdict `concept`. It breaks `one-outline` and the invariant "the outline is a square"; the outline is 7 by 13.
- `crop-extent`: which cells of the box are kept
    - `concept`: the whole box, outline included.
    - `$InteriorOnly`: replaces `crop-outline` with "the output is the cells of the box strictly inside the outline". Fails Fit at train0: it gives a 5 by 5 grid, and the output is 7 by 7.
- `box-source` & `box-shape`, `box-source` & `crop-extent`, `box-shape` & `crop-extent`, `adjacency` & `box-shape`, `adjacency` & `crop-extent`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Restoring the plaid under the outline, or inside it: every pair copies the box's cells as they are.

## Tickets filed
- 10-558_task_c909285e_analyze.md
