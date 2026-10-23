# cc9053aa

## Concept
- Two markers outside a network of walls are the ends of a wire: lay the wire along the walls from one marker to the other, keeping clear of every hazard cell, even at a corner.

## Scene
- `background`: every cell outside the walls, the markers and the hazards is `background_color`.
- `wall-network`: the cells of `wall_color` form one 4-connected structure of 1-wide straight wall lines.
- `two-markers`: exactly two cells are `marker_color`, each on the grid edge outside the walls and 4-adjacent to exactly one wall cell, its contact cell.
- `hazards`: one or more cells are `hazard_color`, each inside the structure's bounding box, in a wall line or in a room between walls.
- `one-clear-route`: of the wall cells that touch no hazard cell in their 8-neighborhood, the 4-connected walks from one contact cell to the other all visit the same cells, so one simple route joins them.

## Rules
- `clear-walls`: a wall cell is clear when no cell of its 8-neighborhood is `hazard_color`.
- `route`: the route is the fewest-hop 4-connected walk of clear wall cells from one marker's contact cell to the other's.
- `paint-route`: each cell of the route becomes `marker_color`; every other cell keeps its input color.

## Parameters
- `wall_color`: 8
- `marker_color`: 9
    - also the color the route is painted
- `hazard_color`: 7

## Scene parameters
- `background_color`: 0
