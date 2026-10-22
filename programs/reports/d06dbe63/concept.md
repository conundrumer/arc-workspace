# d06dbe63

## Concept
- From a single marker, a staircase of a fixed color climbs toward two opposite corners until it leaves the grid.

## Scene
- `one-marker`: every input is a field of `background` with exactly one cell of `marker_color`.

## Rules
- `staircase`: toward each corner of `diag_axis`, a path of `path_color` leaves each marker and repeats one step: `leg` cells along `first_axis` toward that corner's direction on that axis, then `leg` cells across toward the corner's direction on the other axis, each leg starting from the end of the one before.
- `clip`: the path is drawn only where it is in the grid, and it stops at the grid edge.
- `keep-rest`: every non-background input cell, and every cell no path reaches, keeps its input color.

## Parameters
- `path_color`: 5
- `diag_axis`: the anti-diagonal (top-right and bottom-left)
    - the axis whose two corners the staircase climbs toward
- `first_axis`: V
    - the axis of the leg that leaves the marker
- `leg`: 2
    - the number of cells in each leg

## Scene parameters
- `background`: 0
- `marker_color`: 8
