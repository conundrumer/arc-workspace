# db3e9e38

## Concept
- Fits every pair (train0, train1, test0), and every rule has a relational form: the staircase is bounded by the two diagonals from the line's far end, and the color of a column is the parity of its distance from the line.
- No witness has the verdict `other`.
- Three witnesses take a branch's verdict over the concept: `line-from-bottom` (`$EdgeFromLine`), `background=DominantColor` (`background=DominantColor`) and `two-lines` (`$PerLine`). On each of them the concept breaks `hanging-line`, and the concept is either undefined there or gives the steps hanging the wrong way.

## Choice points
- `anchor-edge`
    - `concept`: `anchor_edge` stored as the top edge
        - `stair-extent`
            - `concept`: `staircase-length`: the column at distance d covers the line's rows from its end at the anchor edge, less d cells at the far end
            - `$ToEdge`: replaces `staircase-length`: the column at distance d, the line's column included, fills from the anchor edge to d cells short of the line's far end. Undefined nowhere the concept is defined. Fits every pair. Witness `floating-line`, which breaks `hanging-line` (the line touches the top edge), at the stored assignment, `borderline`, verdict `concept`. It breaks the invariant that every line starts at row 0.
            - `$EdgeAligned`: replaces `staircase-length`: the column at distance d, the line's column included, fills L - d cells from the anchor edge, wherever the line lies. Undefined nowhere the concept is defined. Fits every pair. Witness `floating-line`, which breaks `hanging-line` (the line touches the top edge), at the stored assignment, `borderline`, verdict `concept`. It breaks the invariant that every line starts at row 0.
    - `$EdgeFromLine`: replaces the stored `anchor_edge` with the edge the line touches, the line horizontal or vertical. Undefined where the line touches no edge or two edges. Fits every pair. Witness `line-from-bottom`, which breaks `hanging-line` (the line touches the top edge), at the stored assignment, `variant`, verdict `$EdgeFromLine`. It breaks the invariant that every line touches the top edge.
- `even-color`
    - `concept`: `alternating-color`: a column at even distance takes the line's color
    - `$StoredEvenColor`: replaces `alternating-color`: a column at even distance takes a stored color, 7. Undefined nowhere the concept is defined. Fits every pair. Witness `recolored-line`, which breaks `hanging-line` (the line is of `line_color` 7), at the stored assignment, `variant`, verdict `concept`. It breaks the invariant that every line is 7.
- `stripe-color`
    - `concept`: `stripe_color` stored as 8
    - `$StripeByLineColor`: replaces `stripe_color` with a table `stripe_of_line` from the line's color to the stripe color, {7 -> 8}. Undefined where the line's color is no key of the table. Fits every pair (every pair's key is 7). Witness `recolored-line-keyed`, which breaks `hanging-line` (the line is of `line_color` 7), at the assignment `stripe_of_line` = {7 -> 8, 3 -> 2}, `variant`, verdict `concept`. It breaks the invariant that every line is 7.
    - `stripe_color=OutNewColor`, `stripe_color=AnyOutNewColor`: derive `stripe_color` as the color in the train outputs and in no input. Undefined on every input, since a run has `ex_out` empty. Fail Fit at train0.
    - `stripe_color=DominantColor`, `stripe_color=RarestColor`, `stripe_color=SharedColor`: derive `stripe_color` from the inputs, as 0, 7, and both 0 and 7. Fail Fit at train0.
- `background`
    - `concept`: `background` stored as 0
    - `background=DominantColor`: derives `background` as the commonest color of the input. Undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`, which breaks `hanging-line` (the field is of `background` 0), at the stored assignment, `variant`, verdict `background=DominantColor`. It breaks the invariant that every field is 0.
    - `background=RarestColor`: derives `background` as the rarest color, 7. Fails Fit at train0.
    - `background=SharedColor`: derives `background` as each color in every input, 0 and 7. Fails Fit at train0.
- `line-count`
    - `concept`: `hanging-line`: one line, and the model is undefined where the non-background cells are not one line
    - `$PerLine`: replaces the one line of `hanging-line` with each line, each growing its own staircase. Undefined where two staircases give one cell different colors. Fits every pair. Witness `two-lines`, which breaks `hanging-line` (one line), at the stored assignment, `variant`, verdict `$PerLine`. It breaks the invariant that every input holds one line.
- `parity-origin`
    - `concept`: `alternating-color`: parity of the distance from the line
    - `$AbsoluteParity`: replaces `alternating-color`: the parity of the column index, against a stored phase. Fails Fit at train1 at the phase train0 sets (the line is in col 3 in train0 and col 2 in train1), and at train0 at the other phase.
- `anchor-edge` & `even-color`, `anchor-edge` & `stripe-color`, `anchor-edge` & `background`, `anchor-edge` & `line-count`, `anchor-edge` & `parity-origin`, `even-color` & `stripe-color`, `even-color` & `background`, `even-color` & `line-count`, `even-color` & `parity-origin`, `stripe-color` & `background`, `stripe-color` & `line-count`, `stripe-color` & `parity-origin`, `background` & `line-count`, `background` & `parity-origin`, `line-count` & `parity-origin`, `stair-extent` & `even-color`, `stair-extent` & `stripe-color`, `stair-extent` & `background`, `stair-extent` & `line-count`, `stair-extent` & `parity-origin`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored step for each column (each column one cell shorter than its inner neighbor): the pairs give the step one value, and the steps follow the diagonals from the line's far end. A step of another size is a slope that no pair shows and no element of D4 gives.
- A diagonal line with a diagonal staircase: a diagonal is another orientation type, and that needs another program.
- Staircase cells over other content: no input holds content other than the line.
- Alternation by rows in place of columns: no reader of these pairs takes it, and every pair refutes it.

## Tickets filed
- `10-786_task_db3e9e38_analyze.md`
