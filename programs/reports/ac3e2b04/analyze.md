# ac3e2b04

## Concept
- Fits every pair: train 0–3 and test 0 (`check_concept.py`, and `concept` in `probe.py`).
- Every rule has a relational form, so the concept file's rules are the rules as the generator applies them, with no approximation.
- No witness with verdict `other` was found.
- The concept is undefined where a mark's center lies on lines of both axes, which breaks `parallel-lines`.

## Choice points
- `crossing-frame-shape`
    - `concept`: the frame at a crossing is the eight cells around it (`cross-frame`)
    - `$CopyMark`: replaces `cross-frame`; at each crossing, `draw_color` goes on the cells at the offsets, from the mark's center, of the `mark_color` cells joined to the mark's ring; parameters as the concept's; undefined nowhere the concept is defined. Fits every pair.
        - witness `copy-mark`: breaks `marks` (a 5×5 mark); stored assignment; `borderline` `$CopyMark`; breaks the invariant that every mark is a 3×3 ring.
- `marked-crossing`
    - `concept`: a crossing that a mark surrounds keeps the mark (`cross-frame`, `keep`)
    - `$RepaintMarks`: replaces `cross-frame` and `keep`; a crossing that a mark surrounds takes the frame too, over the mark; parameters as the concept's; undefined nowhere the concept is defined. Fits every pair.
        - witness `aligned-marks`: breaks `one-mark-per-line` (two marks on one row); stored assignment; `variant` `concept`; breaks the invariant that no two marks lie on one perpendicular line.
- `crossed-line`
    - `concept`: a crossing is a cell where the new line meets a full-length line (`cross-frame`)
    - `$AnyLineCell`: replaces `cross-frame`; a frame surrounds each `line_color` cell the new line meets, other than the mark's own center, whether or not a full-length line holds it; parameters as the concept's; undefined nowhere the concept is defined. Fits every pair.
        - witness `partial-line`: breaks `parallel-lines` (a line that stops short of the grid's edges); stored assignment; `borderline` `$AnyLineCell`; breaks the invariant that every line runs the full length or width of the grid.
- `mark-center`
    - `concept`: a mark surrounds a `line_color` cell (`marks`, `cross-line`)
    - `$AnyCenterMark`: replaces `marks` as `cross-line` reads it; a mark is a 3×3 ring of `mark_color` around a cell of any other color, and a mark on no line sends its new line across the axis of the input's lines; parameters as the concept's; undefined on an input with a mark on no line whose lines lie on no axis or on both. Fits every pair.
        - witness `ring-off-line`: breaks `marks` (a ring around a background cell); stored assignment; `borderline` `concept`; breaks the invariant that every mark surrounds a line cell.
- `crossing-cell`
    - `concept`: the new line paints background cells, so a crossing cell keeps `line_color` (`cross-line`)
    - `$OverpaintCrossing`: replaces `cross-line`; the new line paints every cell on it outside the marks; parameters as the concept's; undefined nowhere the concept is defined. Fails Fit at train 0: (6,5) is 2 in the output, and the branch paints it 1.
- `frame-paint`
    - `concept`: a frame paints every cell it covers, line cells included (`cross-frame`)
    - `$FrameOverBackground`: replaces `cross-frame`; a frame paints only the background cells it covers; parameters as the concept's; undefined nowhere the concept is defined. Fails Fit at train 0: (6,4) and (6,6) are 1 in the output, and the branch keeps them 2.
- `line-extent`
    - `concept`: the new line runs across the whole grid (`cross-line`)
    - `$StopAtLastLine`: replaces `cross-line`; the new line runs from the mark only as far as the farthest line it crosses on each side; parameters as the concept's; undefined nowhere the concept is defined. Fails Fit at train 0: rows 8–9 of col 5 are 1 in the output, past the frame around the row-6 crossing.
- `line_color`
    - `concept`: stored, 2
    - `line_color=derived`: replaces the stored `line_color`; the program derives it as the color of each cell whose eight neighbors are all `mark_color`; undefined on an input where those cells hold no color or more than one. Fits every pair.
        - witness `line_color=derived`: breaks `parallel-lines` and `marks` (the lines and the mark's center are 4); stored assignment; `variant` `line_color=derived`; breaks the invariant that the lines are 2.
- `mark_color`
    - `concept`: stored, 3
    - `mark_color=derived`: replaces the stored `mark_color`; the program derives it as the one color, other than `line_color` and `background`, of all eight neighbors of a `line_color` cell; undefined on an input where that gives no color or more than one. Fits every pair.
        - witness `mark_color=derived`: breaks `marks` (the mark is 6); stored assignment; `variant` `mark_color=derived`; breaks the invariant that the marks are 3.
    - `mark_color=RarestColor`: replaces the stored `mark_color`; the input's rarest color; undefined on an input where colors tie for the fewest cells. Fits every pair.
        - witness `mark_color=RarestColor`: breaks no scene claim (a 7×7 grid whose one line has fewer cells than its mark); stored assignment; `ordinary` `concept`.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: replaces the stored `background`; the input's commonest color; undefined on an input where colors tie for the most cells. Fits every pair.
        - witness `background=DominantColor`: breaks `parallel-lines` (the field is 5); stored assignment; `variant` `background=DominantColor`; breaks the invariant that the field is 0.
- `draw_color`
    - `concept`: stored, 1
    - `draw_color=OutNewColor`: replaces the stored `draw_color`; a color in every train output and in no input; undefined on every input, since the run on one input has no `ex_out`. Fails Fit at train 0, where it gives no value.
    - `draw_color=AnyOutNewColor`: replaces the stored `draw_color`; a color in some train output and in no input; undefined on every input, for the same reason. Fails Fit at train 0, where it gives no value.
- `crossing-frame-shape` & `marked-crossing`, `crossing-frame-shape` & `crossed-line`, `crossing-frame-shape` & `mark-center`, `crossing-frame-shape` & `crossing-cell`, `crossing-frame-shape` & `frame-paint`, `crossing-frame-shape` & `line-extent`, `crossing-frame-shape` & `line_color`, `crossing-frame-shape` & `mark_color`, `crossing-frame-shape` & `background`, `crossing-frame-shape` & `draw_color`, `marked-crossing` & `crossed-line`, `marked-crossing` & `mark-center`, `marked-crossing` & `crossing-cell`, `marked-crossing` & `frame-paint`, `marked-crossing` & `line-extent`, `marked-crossing` & `line_color`, `marked-crossing` & `mark_color`, `marked-crossing` & `background`, `marked-crossing` & `draw_color`, `crossed-line` & `mark-center`, `crossed-line` & `crossing-cell`, `crossed-line` & `frame-paint`, `crossed-line` & `line-extent`, `crossed-line` & `line_color`, `crossed-line` & `mark_color`, `crossed-line` & `background`, `crossed-line` & `draw_color`, `mark-center` & `crossing-cell`, `mark-center` & `frame-paint`, `mark-center` & `line-extent`, `mark-center` & `line_color`, `mark-center` & `mark_color`, `mark-center` & `background`, `mark-center` & `draw_color`, `crossing-cell` & `frame-paint`, `crossing-cell` & `line-extent`, `crossing-cell` & `line_color`, `crossing-cell` & `mark_color`, `crossing-cell` & `background`, `crossing-cell` & `draw_color`, `frame-paint` & `line-extent`, `frame-paint` & `line_color`, `frame-paint` & `mark_color`, `frame-paint` & `background`, `frame-paint` & `draw_color`, `line-extent` & `line_color`, `line-extent` & `mark_color`, `line-extent` & `background`, `line-extent` & `draw_color`, `line_color` & `background`, `line_color` & `draw_color`, `mark_color` & `background`, `mark_color` & `draw_color`, `background` & `draw_color`: the two branches' changes applied together
- `line_color` & `mark_color`: the two branches' changes applied together
    - `line_color=derived` & `mark_color=derived`: each derivation reads the other's value, so the model reads them jointly: a mark is a 3×3 ring of one color other than `background` around a cell of another color, `mark_color` is the ring's color and `line_color` the center's, undefined on an input where that gives no pair of colors or more than one.

## Open parameters
- none

## Not formed
- `line_color` from a proposer: `SharedColor` gives every color of an input (0, 2 and 3 here), and `CountRankAsc` and `CountRankDesc` give a ranking of colors, so no proposer gives `line_color` alone.
- A parameter for the mark's size: `marks` fixes the 3×3 ring as the structure of the task, and `$CopyMark` is the reading in which the frame follows the mark's size.
- Under `$AnyCenterMark`, a mark on no line that sends new lines on both axes: no source that step 1 lists gives that reading.

## Tickets filed
- none
