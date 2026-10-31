# fb791726

## Concept
- Lay the picture out twice along the diagonal of a grid twice its size, and wherever two marks stand one cell apart in a column, draw a full-width line of `3` through the row between them.

## Scene
- `square-field`: each input is a square field of `background`.
- `one-mark-color`: the input's non-background cells all have one color.
- `marks-in-pairs`: the marks come in pairs on one column, `pair_gap` cells apart along the `pair_axis` axis, with background between them.

## Rules
- `diagonal-copies`: the output is `copy_count` times the input's extent on each axis; the input is copied into each block on the `copy_diag` diagonal, and every other block is background.
- `bridge-lines`: in every row that lies between two marks of one column standing `pair_gap` apart along `pair_axis`, in any copy, each cell across the whole output's width takes `line_color`.

## Parameters
- `line_color`: 3
- `copy_count`: 2
    - the number of copies, and the output's scale on each axis
- `copy_diag`: the top-left to bottom-right diagonal
    - which diagonal of blocks receives the copies
- `pair_axis`: vertical
    - the axis the two marks of a pair share a column along; the lines run on the other axis
- `background`: 0
- `pair_gap`: 2
    - the distance between the two marks of a pair, so one cell lies between them

## Scene parameters
- none
