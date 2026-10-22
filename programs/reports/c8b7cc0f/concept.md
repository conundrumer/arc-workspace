# c8b7cc0f

## Concept
- Count the dots that sit inside the box, and fill that many cells of a small grid, in reading order, with the dot color.

## Scene
- `box-outline`: a one-cell-wide rectangle outline of `frame_color` on a `background` field, with at least one row and one column of interior.
- `scattered-dots`: single cells of one other color, the dot color, inside and outside the outline; the dot color differs between pairs.
- `count-fits`: the number of dots inside the outline is at most the number of cells of the output grid.

## Rules
- `count-inside`: the count is the number of dot cells strictly inside the outline.
- `fill-in-order`: the output is an `out_size` grid of `background`, where the first `count` cells, in the order that starts at `fill_corner` and sorts by `fill_primary_axis` first, take the dot color.

## Parameters
- `frame_color`: 1
- `background`: 0
- `out_size`: 3×3
- `fill_corner`: top-left
    - the corner the fill starts at
- `fill_primary_axis`: V
    - the axis whose coordinate orders the cells first, so the fill runs along a row before it steps to the next row

## Scene parameters
- none
