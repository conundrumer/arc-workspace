# d4c90558

## Concept
- Count the gray dots inside each colored frame, and draw a bar chart: one bar per frame, in the frame's color, as long as its dot count, with the bars stacked from shortest to longest.

## Scene
- `background`: the background is `background_color`.
- `frames`: the input holds several frames, each a closed rectangular outline of one color, with no two frames of one color; a frame may have one or more sides thicker than one cell.
- `marks-inside`: each frame's enclosed region holds cells of color `mark_color`, scattered on background, and no other color; no `mark_color` cell lies outside a frame.
- `distinct-counts`: no two frames hold the same number of `mark_color` cells.

## Rules
- `count`: each frame's count is the number of `mark_color` cells in the region it encloses.
- `bar`: each frame gives one line of the output, filled from the `bar_start` edge with the frame's color for as many cells as its count, and background after.
- `order`: the lines are ordered by count, the smallest count at the `short_end` edge.
- `size`: the output has one line per frame, and each line is as long as the largest count.

## Parameters
- `mark_color`: `5`
- `bar_start`: left
    - the edge of the output each bar starts from
- `short_end`: top
    - the edge of the output where the bar of the smallest count sits
- `background_color`: `0`

## Scene parameters
- none
