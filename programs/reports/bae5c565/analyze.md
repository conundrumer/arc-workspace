# bae5c565

## Concept
- The concept case fits every pair: train0, train1 and test0 give the expected output.
- Every rule has a relational form, and no witness has the verdict `other`.
- Six choice points stand at the concept. Each has a non-concept branch that fits every pair, so each of the concept's scene claims `background-field`, `palette-row` and `stalk` is broken by a witness that separates a branch.

## Choice points
- `background`
    - `concept`: `background` is stored, 5
    - `background=DominantColor`: replaces the stored `background` with the input's commonest color, read by `clear-palette`, `keep-stalk` and `rest-background`; undefined on an input where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`: the field is 4. It breaks `background-field` at the stored assignment, where the concept finds no stalk and is undefined. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that the field is 5 in every input.
    - `background=SharedColor`: replaces the stored `background` with each color present in the input; on one input alone that is every color of the input, so the model has no single background and is undefined. Fails Fit at train0.
- `palette_side`
    - `concept`: `palette_side` is stored, top
    - `$PaletteSideFromInput`: replaces the stored `palette_side` with the edge whose line holds the most non-background cells; reads `background`; undefined where two edges tie for that count. Fits every pair. Witness `palette-on-left`: train1's input transposed, so the palette is the left column and the stalk runs along the middle row from the right edge. It breaks `palette-row` at the stored assignment, where the concept finds no stalk and is undefined. Plausibility `variant`, verdict `$PaletteSideFromInput`. It breaks the invariant that the palette is the top row in every input.
- `column-extent`
    - `concept`: `stepped-fill` runs each column from d rows past the stalk's end nearest the palette to the edge opposite `palette_side`
    - `$FillToStalkEnd`: replaces `stepped-fill`: each column's run stops at the row of the stalk's end farthest from the palette, so the mountain stands on the stalk's base; parameters and undefined inputs those of the concept. Fits every pair. Witness `floating-stalk`: train1's stalk ends two rows short of the bottom edge. It breaks `stalk` (the stalk runs from the edge opposite `palette_side`). Plausibility `borderline`, verdict `$FillToStalkEnd`. It breaks the invariant that the stalk reaches the bottom edge in every input.
    - `$HeightFromStalkLength`: replaces `stepped-fill`: a column at distance d less than the stalk's length L gets L − d cells stacked from the edge opposite `palette_side`; parameters and undefined inputs those of the concept. Fits every pair. Witness `floating-stalk`, as for `$FillToStalkEnd`, where this branch gives a third output.
- `stalk-color`
    - `concept`: `keep-stalk` keeps the stalk's own color
    - `$StalkTakesPaletteColor`: replaces `keep-stalk`: the stalk takes the palette color of its column where that color is not `background`; parameters and undefined inputs those of the concept. Fits every pair. Witness `stalk-palette-color`: train1 with 3 in the palette cell above the stalk. It breaks `palette-row` (`background` in the stalk's column). Plausibility `borderline`, verdict `concept`. It breaks the invariant that the palette cell above the stalk is `background` in every input.
- `distance-origin`
    - `concept`: `stepped-fill` measures d from the stalk's column
    - `$DistanceFromCenter`: replaces the d of `stepped-fill` with the distance from the grid's center column; undefined on an even width. Fits every pair. Witness `off-center-stalk`: a 9×9 input whose stalk and palette gap stand in col 3. It breaks `stalk` (the stalk runs along the center column). Plausibility `borderline`, verdict `concept`. It breaks the invariant that the stalk stands in the center column in every input.
- `stalk-find`
    - `concept`: the stalk is the non-`background` cells off the palette row
    - `$StalkByColor`: replaces `keep-stalk`: the stalk is the cells of `stalk_color` off the palette row, and any other non-`background` cell there becomes `background`; `stalk_color` moves from Scene parameters to Parameters; undefined where those cells are not one unbroken run in one column, none included. Fits every pair. Witness `stray-cell`: train1 with a stray 3 at (1,0). It breaks `background-field`, and the concept is undefined there. Plausibility `foreign`, verdict `$StalkByColor`.
- `background` & `palette_side`, `background` & `column-extent`, `background` & `stalk-color`, `background` & `distance-origin`, `background` & `stalk-find`, `palette_side` & `column-extent`, `palette_side` & `stalk-color`, `palette_side` & `distance-origin`, `palette_side` & `stalk-find`, `column-extent` & `stalk-color`, `column-extent` & `distance-origin`, `column-extent` & `stalk-find`, `stalk-color` & `distance-origin`, `stalk-color` & `stalk-find`, `distance-origin` & `stalk-find`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- a step other than one row per column: the pairs fix the step at one row per column.
- a palette row that stays in the output: the pairs clear it to `background`.
- a parameter of its own for the edge the mountain stands on: that edge follows from `palette_side` in every variant task, so it is derived data.
- column colors read from the mirrored palette position: train0's palette is not symmetric, and the pairs fix each column's color to the palette cell above it.
- a reading of `stalk-reach` where a short stalk changes the outer columns: every reading gives a column with no cells where d rows past the stalk's end leave the grid, so no model departs.
- derivations of `background` by `VanishedColor`, `ChangedColor` or `UnchangedColor`: they read `ex_out`, which is empty in a run on one input, and none of them reads a background.

## Tickets filed
- 10-457_task_bae5c565_analyze.md
