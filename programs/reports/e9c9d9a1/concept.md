# e9c9d9a1

## Concept
- Lines that run the full width and full height cut the grid into a table of rooms. Each corner room gets its own corner color, the inner rooms that touch no grid edge get one fill color, and the other edge rooms stay empty.

## Scene
- `full-lines`: lines of `line_color`, each one cell wide, run across the full width or the full height of the grid on a field of `background`.
- `two-lines-per-axis`: on each axis there are at least two lines, so there are at least three rooms across each axis and at least one inner room.
- `no-edge-line`: no line is on the grid edge, and no two lines are adjacent, so each room is a nonempty rectangle.

## Rules
- `corner-rooms`: each of the four corner rooms is filled with the color `corner_color` gives for its corner.
- `inner-rooms`: each room that touches no grid edge is filled with `inner_color`.
- `rest-unchanged`: the lines and the edge rooms that are not corner rooms keep their input cells.

## Parameters
- `corner_color`: top-left `2`, top-right `4`, bottom-left `1`, bottom-right `8`
    - the fill color of each corner room, keyed by corner
- `inner_color`: `7`
- `background`: `0`
    - the color of the cells in a room, which the program reads to find the rooms

## Scene parameters
- `line_color`: `3`
