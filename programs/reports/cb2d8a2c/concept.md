# cb2d8a2c

## Concept
- A path is drawn from a marker on one edge across to the opposite edge, and it detours around each wall in its way, keeping from that wall a gap as wide as the number of marks on the wall; the marks are then erased into the wall.

## Scene
- `background`: every cell that is not part of a source or a wall is `background`.
- `source`: one cell of `path_color` lies on one edge of the grid; the direction from that edge to the opposite edge is the direction of travel.
- `walls`: each wall is a straight segment one cell wide, perpendicular to the direction of travel, that touches one of the two edges parallel to the direction of travel and ends inside the grid.
- `wall-marks`: each wall is `wall_color` with `mark_color` cells at every second cell, starting at the cell on the edge; the count of `mark_color` cells is the wall's clearance.
- `walls-in-order`: the walls lie at distinct distances from the source's edge, and each one crosses the line the path follows when it comes to that wall.
- `room`: each detour fits in the grid, with its clearance on each side of the wall's free end and before the wall, and does not touch another wall.

## Rules
- `erase-marks`: each `mark_color` cell becomes `wall_color`; the walls are otherwise unchanged.
- `path`: a line of `path_color` runs from the source in the direction of travel. When the path comes to a wall, it stops on the line with `clearance` cells between it and the wall, turns toward the wall's free end, runs past that end until `clearance` cells lie between it and the end, and turns back to the direction of travel. After the last wall, it runs on to the opposite edge.
- `clearance`: the gap the path keeps from a wall, before the wall and past its free end, is the count of `mark_color` cells on that wall.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `path_color`: 3
- `wall_color`: 2
- `mark_color`: 1

## Scene parameters
- `background`: 8
