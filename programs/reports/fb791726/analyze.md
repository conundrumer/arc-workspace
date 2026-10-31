# fb791726

## Concept
- Fits every pair (train0–2, test0), checked by `work/task/fb791726/check.py`. The output is `copy_count` = 2 times the input on each axis. The input is copied onto the top-left to bottom-right diagonal of blocks. Each row lying between two marks of one column `pair_gap` = 2 apart along `pair_axis` = vertical becomes a full-width line of `line_color` = 3.
- No witness has verdict `other`. The rule as the generator applies it is the rule the concept file states. It is relational (marks, columns, rows between them, copies), so it is not an approximation.
- The diagonal copies take disjoint columns, so the same-column pairing never links marks of two copies. Finding the bridged rows on the input or on the output canvas gives one model under the concept. That choice only matters under `$BridgeAcrossColumns`.

## Choice points
- `pair-distance`
    - `concept`: the two marks bracketing a line stand exactly `pair_gap` apart in their column
    - `$BridgeAnyGap`: replaces `bridge-lines`. Every row strictly between two consecutive marks of one column takes `line_color` across the full width. Drops `pair_gap`. Defined on every input. Fits every pair. Witness `bridge-wide-gap`: breaks `marks-in-pairs` (`pair_gap`), plausibility `variant`, verdict `$BridgeAnyGap`. The invariant it breaks is that every two marks in a column stand two apart.
- `pair-alignment`
    - `concept`: the two bracketing marks share a column
    - `$BridgeAcrossColumns`: replaces `bridge-lines`. A row of the output canvas whose rows above and below each hold a mark, in any columns, becomes a full-width line. Defined on every input. Fails Fit at test0: row 3 lies between copy 1's mark at (2,0) and copy 2's mark at (4,4), so it gets a line where test0 output row 3 is background.
        - `bridge-frame`
            - `concept`: bridged rows are found on the output canvas
            - `$PerCopy`: bridged rows are found within each copy (on the input) and drawn full width in the output. Defined on every input. Fits every pair. Witness `bridge-unaligned-marks`: breaks `marks-in-pairs` (alignment), plausibility `borderline`, verdict `concept`. The invariant it breaks is that the two marks around a gap row stand in one column.
- `pair-axes`
    - `concept`: pairs along the stored `pair_axis` alone
    - `$BridgeBothAxes`: replaces `bridge-lines`. Pairs along either axis bridge, and a horizontal pair draws a full-height line down the column between its marks. Drops `pair_axis`, since the program runs over every axis. Defined on every input. Fits every pair. Witness `bridge-horizontal-pair`: breaks `marks-in-pairs` (`pair_axis`), plausibility `variant` (a transposed variant task contains it routinely), verdict `$BridgeBothAxes`. The invariant it breaks is that every pair is vertical.
- `line-overwrite`
    - `concept`: the line paints every cell of its row, marks included
    - `$LineKeepsMarks`: replaces `bridge-lines`. The line paints only background cells, and a mark in a line row keeps its color. Defined on every input. Fits every pair. Witness `line-crosses-mark` (two interleaved pairs): breaks no scene claim, plausibility `ordinary`, verdict `any`.
- `line-extent`
    - `concept`: the line spans the whole output width
    - `$LineInCopy`: replaces `bridge-lines`. The line spans only the columns of the copy whose pair it bridges. Defined on every input. Fails Fit at train0: output row 1, cols 6–11 are `3`.
- `line_color` source
    - `concept`: stored, 3
    - `line_color=OutNewColor`: derived on one input with `ex_out` empty. `uniform` then has no rows, so it proposes nothing, and the branch is undefined on every input. Fails Fit at train0.
    - `line_color=AnyOutNewColor`: derived the same way. With no output it proposes nothing, so it is undefined on every input. Fails Fit at train0.
- `pair-distance` & `pair-alignment`, `pair-distance` & `pair-axes`, `pair-distance` & `line-overwrite`, `pair-distance` & `line-extent`, `pair-distance` & `line_color` source, `pair-distance` & `bridge-frame`, `pair-alignment` & `pair-axes`, `pair-alignment` & `line-overwrite`, `pair-alignment` & `line-extent`, `pair-alignment` & `line_color` source, `pair-axes` & `line-overwrite`, `pair-axes` & `line-extent`, `pair-axes` & `line_color` source, `pair-axes` & `bridge-frame`, `line-overwrite` & `line-extent`, `line-overwrite` & `line_color` source, `line-overwrite` & `bridge-frame`, `line-extent` & `line_color` source, `line-extent` & `bridge-frame`, `line_color` source & `bridge-frame`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `copy_count` derived: no fact of one input gives 2 (the pair counts are 2, 1, 1, 1). ScaleRatio and ScaleRatioAxis read outputs and propose nothing on one input. A derived branch is undefined everywhere and is the same as storing nothing, so the stored count stays.
- `line_color` derived by an input-only proposer (SharedColor, DominantColor, RarestColor, CountRank*): no input contains `3`, so none of them gives 3, and each fails Fit at train0. They are not listed one by one.
- Copies on the other diagonal, or another block arrangement: the pairs fix `copy_diag`. Another value is a reassignment, not a branch.
- Bridged rows found per input rather than on the canvas, under the concept: the copies take disjoint columns, so this is the concept's own model. It is a point only under `$BridgeAcrossColumns` (`bridge-frame`).

## Tickets filed
- none
