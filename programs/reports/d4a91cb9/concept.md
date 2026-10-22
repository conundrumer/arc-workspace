# d4a91cb9

## Concept
- Two single marked cells are joined by an L-shaped path: it leaves the first mark along a column, turns once, and runs along the row of the second mark until it meets that mark.

## Scene
- `two-marks`: the input holds exactly two non-background cells, one of color `start_color` and one of color `end_color`, on a field of `bg`.
- `marks-off-line`: the two marks share no row and no column.

## Rules
- `l-path`: the output is the input with color `path_color` painted on the cells of the leg that runs from the `start_color` mark along `start_axis` to the line of the `end_color` mark, and on the cells of the leg that runs from that corner along the other axis to the `end_color` mark; the two marks keep their colors.
- `corner`: the path turns at the cell that shares the `start_color` mark's line on `start_axis` and the `end_color` mark's line on the other axis.

## Parameters
- `start_color`: 8
    - the color of the mark the first leg leaves from
- `end_color`: 2
    - the color of the mark the second leg ends at
- `path_color`: 4
- `start_axis`: vertical
    - the axis of the leg that leaves the `start_color` mark

## Scene parameters
- `bg`: 0
