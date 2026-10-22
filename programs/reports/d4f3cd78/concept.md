# d4f3cd78

## Concept
- A box with one hole in its wall fills up with water, and the water runs out through the hole in a straight stream to the edge of the grid.

## Scene
- `one-walled-box`: one rectangular outline of `wall_color`, at least 3 cells on each side, on a field of `background`, with an empty interior.
- `one-gap`: the outline lacks exactly one cell, which is on a side and not at a corner.

## Rules
- `fill-interior`: each cell inside the outline becomes `fill_color`.
- `fill-gap`: the gap cell becomes `fill_color`.
- `stream-out`: from the gap, each cell in a straight line outward, perpendicular to the gap's side and away from the interior, becomes `fill_color`, up to the grid edge.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `fill_color`: 8
- `wall_color`: 5

## Scene parameters
- `background`: 0
