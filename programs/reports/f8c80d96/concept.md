# f8c80d96

## Concept
- Nested rectangle outlines, each the last one grown by a fixed step on every side and cut off by the grid edge, keep growing outward until they leave the grid, and the empty cells turn `fill_color`.

## Scene
- `background-field`: every cell that is not on an outline holds `background`.
- `one-line-color`: every outline cell holds the one other color of the input, the line color.
- `nested-outlines`: the line cells are the visible cells of two or more rectangle outlines, 1 cell thick, each of which reaches past the grid edge on one or more sides.
- `uniform-step`: each outline is the next inner one moved outward by one step on every side, the same step for every two consecutive outlines.

## Rules
- `grow-outward`: the output holds the input's outlines and every further outline that the step gives outward from the outermost one, drawn in the line color where it falls in the grid, up to the first outline that falls wholly outside the grid.
- `fill-rest`: every other output cell holds `fill_color`.

## Parameters
- `background`: 0
- `fill_color`: 5

## Scene parameters
none
