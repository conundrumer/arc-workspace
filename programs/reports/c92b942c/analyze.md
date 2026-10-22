# c92b942c

## Concept
- Fits every train pair and the test pair (`work/task/c92b942c/probe.py`). Each rule has a relational form, and no witness has the verdict `other`.
- Collisions between decorations never occur in the evidence. In every tiled input, the rows that hold marks are at least two apart, so no corner lands on a line or on a mark. The concept's paint order is the concept branch of the two points below that cover those collisions.

## Choice points
- `decorate-frame`: the frame the corner steps are taken in
    - `concept`: the tiled grid; a step that leaves it paints nothing
    - `$InputFrame`: replaces `diag-corners` and `row-line`; the input is decorated in its own frame, clipped at its edges, and then tiled; defined on every input; fails Fit at train1 (the tiled grid has 3 at `train1 output (1,1)`, the up-left corner of the mark at (2,2), which the input frame clips)
    - `$Torus`: replaces `diag-corners`; a step that leaves the frame wraps to the far edge, which gives one output whether the input or the tiled grid is decorated; defined on every input; fails Fit at train1 (it paints `train1 output (5,1)`, the wrapped up-left corner of the mark at (0,2), where the output has 0)
- `line-corner-order`: the color of a cell that is both on a line and at a corner
    - `concept`: the corner's `diag-color` paints over the line
    - `$LineOverCorner`: replaces `diag-corners`; a corner paints only a cell the line leaves `background`; defined on every input; fits every pair; witness `adjacent-mark-rows`, at the stored assignment, breaks no scene claim, plausibility `variant`, verdict `concept`; it breaks the invariant of the inputs that rows holding marks are at least two apart in the tiled grid
- `corner-mark-order`: the color of a mark at another mark's corner
    - `concept`: the mark keeps its color
    - `$CornerOverMark`: replaces `marks-kept`; a corner paints `diag-color` over a mark; defined on every input; fits every pair; witness `diagonal-marks`, at the stored assignment, breaks no scene claim, plausibility `variant`, verdict `concept`; it breaks the invariant of the inputs that no two marks of the tiled grid are one diagonal step apart
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: the input's commonest color, every tied color on a tie; replaces the stored value read by `row-line`, `diag-corners` and `marks-kept`; defined on every input; fits every pair; witness `background=DominantColor`, at the stored assignment, breaks `marks-on-background` (the 5 marks outnumber the 0 cells), plausibility `borderline`, verdict `concept`; it breaks the invariant of the inputs that 0 is the commonest color of each input
    - `background=SharedColor`: every color of the input, since the derivation runs on that input alone; replaces the same stored value; then no cell is a mark and the output is the tiled input; fails Fit at train0
- `tile-count`
    - `concept`: stored, 3
    - `tile-count=ScaleRatio`: the output-to-input size ratio; replaces the stored value read by `tile`; the derivation reads `ex_out`, which is empty on a run, so it is undefined on every input; fails Fit at train0
- `line-color`
    - `concept`: stored, 1
    - `line-color=OutNewColor`: a color in every train output and no input; replaces the stored value read by `row-line`; undefined on every input for the same reason; fails Fit at train0
- `diag-color`
    - `concept`: stored, 3
    - `diag-color=OutNewColor`: as for `line-color`, read by `diag-corners`; undefined on every input; fails Fit at train0
- `decorate-frame` & `line-corner-order`, `decorate-frame` & `corner-mark-order`, `decorate-frame` & `background`, `decorate-frame` & `tile-count`, `decorate-frame` & `line-color`, `decorate-frame` & `diag-color`, `line-corner-order` & `corner-mark-order`, `line-corner-order` & `background`, `line-corner-order` & `tile-count`, `line-corner-order` & `line-color`, `line-corner-order` & `diag-color`, `corner-mark-order` & `background`, `corner-mark-order` & `tile-count`, `corner-mark-order` & `line-color`, `corner-mark-order` & `diag-color`, `background` & `tile-count`, `background` & `line-color`, `background` & `diag-color`, `tile-count` & `line-color`, `tile-count` & `diag-color`, `line-color` & `diag-color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A line cast from each mark to the grid edges, or stopped at the next mark: on every input it gives the full-row line, since a stop is a mark on the same row whose own line continues it, so its model is equivalent to the concept's.
- A line confined to each tile: tiling repeats the input row, so each tile on a marked row holds a mark and draws the same line; equivalent.
- A line that paints over marks: `train2 output row 3` keeps both 4s, so the pairs separate it.
- A tile count from the inputs alone: the inputs are 3×3, 2×4, 4×6 and 5×5, and no input property or proposer that reads the inputs alone gives 3 on each.
- `line-color` or `diag-color` from the inputs alone: neither 1 nor 3 occurs in any input.
- `line-axis` and `diag-dirs` derived: no proposer gives an axis or a set of corners, and no input fixes them.
- A mark color as a parameter: the marks are 6, 5, 4 and 2 in the train pairs, and the program reads every non-`background` cell as a mark.
- A color per corner, stored as rows keyed by corner: both corners take 3 in every pair, and no source gives a task in which the corners take different colors.

## Tickets filed
- none
