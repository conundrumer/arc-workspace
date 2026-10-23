# e9614598

## Concept
- The concept fits every train pair and both test pairs: on each one, the plus centers on the cell at equal distance from the two marks, `train0 output (4,4)`, `train1 output (4,3)`, `test0 output (3,6)`, `test1 output (3,3)`.
- The rule `midpoint` has a relational form: the center is the cell on the marks' shared line whose distance to one mark equals its distance to the other. The program uses no approximation.
- No witness has the verdict `other`.

## Choice points
- `footprint`
    - `concept`: `plus`, with arms of `arm_length` in every cardinal direction
    - `$StoredFootprint`: replaces `plus`; a stored set of offsets `footprint` from the center takes `plus_color`, and `arm_length` is gone; defined wherever the concept is; fits every pair; witness `stored-footprint`, at `footprint` = a T (center, left, right, down); breaks no scene claim; plausibility `borderline`; verdict `$StoredFootprint`; it breaks no invariant of the inputs, and it breaks the regularity of the outputs that the plus reaches every cardinal direction
- `marks`
    - `concept`: the marks are every non-background cell
    - `$MarkColor`: replaces `two-marks`; the marks are the cells of a stored `mark_color`, other cells keep their color, and `background` is not read; undefined where the input holds other than two cells of `mark_color`, or where the marks are not aligned at an even distance; fits every pair; witness `mark-color`; breaks `two-marks`; plausibility `borderline`; verdict `$MarkColor`; it breaks the invariant that each input holds exactly two non-background cells
- `background`
    - `concept`: `background` is stored, 0
    - `background=DominantColor`: replaces the stored `background` by the commonest color of the input; undefined where two colors tie for the highest count; fits every pair; witness `background=DominantColor`; breaks `background` at the stored value 0; plausibility `variant`; verdict `background=DominantColor`; it breaks the invariant that each input's background is 0
- `plus-color`
    - `concept`: `plus_color` is stored, 3
    - `plus_color=OutNewColor`: replaces the stored `plus_color` by the derivation on one input with `ex_out` empty; that derivation reads no train output, so it does not give 3 as its one value on any input; fails Fit at train0
- `center`
    - `concept`: `midpoint`, on the shared row or column of the two marks
    - `$BoxCenter`: replaces `midpoint` and drops `marks-aligned`; the center is the cell whose row is at equal distance from the two marks' rows and whose column is at equal distance from their columns; undefined where the marks are at an odd distance on either axis; fits every pair; witness `box-center`; breaks `marks-aligned`; plausibility `borderline`; verdict `$BoxCenter`; it breaks the invariant that the two marks share a row or a column
- `pairing`
    - `concept`: exactly two marks, and one plus
    - `$EveryPair`: replaces `two-marks`, `midpoint` and `plus`; a plus is drawn at the center of each two marks that the center rule accepts, and an input with no such pair is kept unchanged; defined on every input; fits every pair; witness `every-pair`; breaks `two-marks`; plausibility `borderline`; verdict `$EveryPair`; it breaks the invariant that each input holds exactly two non-background cells
- `overlap`
    - `concept`: the plus is drawn over every cell it covers
    - `$MarksOnTop`: replaces `keep-input`; a mark under the plus keeps its color; defined wherever the concept is; fits every pair; witness `marks-on-top`; breaks `plus-clear`; plausibility `borderline`; verdict `$MarksOnTop`; it breaks the invariant that the marks are 6 or more cells apart, so that the plus reaches no mark
- `footprint` & `background`, `footprint` & `plus-color`, `footprint` & `center`, `footprint` & `pairing`, `footprint` & `overlap`, `footprint` & `marks`, `marks` & `plus-color`, `marks` & `center`, `marks` & `pairing`, `marks` & `overlap`, `background` & `plus-color`, `background` & `center`, `background` & `pairing`, `background` & `overlap`, `plus-color` & `center`, `plus-color` & `pairing`, `plus-color` & `overlap`, `center` & `pairing`, `center` & `overlap`, `pairing` & `overlap`: the two branches' changes applied together
- `marks` & `background`: the model of `$MarkColor` and the model of `background=DominantColor` in one case
    - `$MarkColor` & `background=DominantColor`: the model of `$MarkColor` alone, because that branch reads no background

## Open parameters
- none

## Not formed
- A plus where the marks are an odd distance apart: no cell is at equal distance from the two marks, and no pair shows content there. Each output that could be drawn there is a choice that no reading of the pairs gives.
- The plus at the grid's center: the train grids are 10 × 10 and have no center cell, and the train1 plus is at column 3 of 10.
- `arm_length` derived from the distance between the marks: the distances are 6 in train0 and 8 in train1, and the arm length is 1 in both, so only a constant fits.
- A plus that is not drawn when it reaches past the grid edge: the plus is drawn only on grid cells under each reading, and clipping is the only reading.
- A `marks` branch with `mark_color` derived by a proposer: the concept reads no `mark_color`, and `$MarkColor` stores it.

## Tickets filed
- none
