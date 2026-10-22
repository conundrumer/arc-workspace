# b942fd60

## Concept
- A red line shoots from the red cell on the grid edge, and each time it is about to hit a colored cell it stops and branches both ways at a right angle; a branch that reaches the grid edge ends there.

## Scene
- `background`: every cell that is not a mark has the color `background`.
- `one-seed`: exactly one cell has the color `line-color`, the seed, and it lies on the grid edge opposite `start-dir`.
- `scattered-marks`: single cells of other colors, the obstacles, lie scattered over the grid; none has the color `line-color`.

## Rules
- `first-ray`: a ray leaves the seed toward `start-dir`.
- `ray-stops`: a ray runs over the cells in its direction, and stops at the last cell before an obstacle or before the grid edge.
- `branch`: where a ray stops before an obstacle, two new rays leave the stop cell, one in each direction perpendicular to that ray.
- `edge-ends`: a ray that stops at the grid edge has no branches.
- `paint`: every cell a ray runs over takes the color `line-color`; every other cell keeps its input color.

## Parameters
- `start-dir`: right
    - the direction the first ray leaves the seed in
- `line-color`: 2
    - the color of the seed and of the rays
- `background`: 0

## Scene parameters
- none
