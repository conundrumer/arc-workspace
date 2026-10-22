# db695cfb

## Concept
- Two marks of one color that share a diagonal are joined by a diagonal line of that color, and each mark of a second color that the line runs through sends out a full diagonal line of the second color, square to the joining line, across the whole grid.

## Scene
- `field-with-single-marks`: a field of one background color, with single cells of `link_color` and any number of single cells of `cross_color` scattered on it.
- `clear-cross-lines`: the full diagonal through each `cross_color` cell that lies between two diagonal `link_color` cells, square to their joining line, holds no other mark and no cell of another joining line.

## Rules
- `join-diagonal-pairs`: each two `link_color` cells on one diagonal are joined by `link_color` on every cell between them on that diagonal.
- `perpendicular-cross`: each `cross_color` cell strictly between two joined `link_color` cells paints `cross_color` on its whole diagonal of the other diagonal axis, out to the grid edges in both directions.
- `cross-over-link`: where a `cross_color` line and a `link_color` line meet, the cell is `cross_color`.
- `rest-unchanged`: every other cell keeps its input color, so a `cross_color` cell off every joining line stays a single cell.

## Parameters
- `link_color`: 1
    - the color of the marks that are joined
- `cross_color`: 6
    - the color of the marks that send out the square lines

## Scene parameters
- none
