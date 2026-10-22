# b7256dcd

## Concept
- Each shape takes the color of the marker cell that touches it, and every marker is erased.

## Scene
- `background`: every cell that is not part of a shape or a marker has the color `background`.
- `shapes`: the shapes are the 4-connected components of the cells of color `shape_color`.
- `markers`: each marker is a single cell whose color is neither `background` nor `shape_color`.
- `one-marker-per-shape`: each shape has exactly one marker cell 4-adjacent to it.
- `marker-touches-at-most-one-shape`: each marker is 4-adjacent to at most one shape; some markers are 4-adjacent to no shape.

## Rules
- `recolor-shape`: each cell of a shape takes the color of the marker 4-adjacent to that shape.
- `erase-markers`: each marker cell takes the color `background`, whether or not it touches a shape.
- `keep-background`: each other cell keeps its color.

## Parameters
- `background`: 7
- `shape_color`: 6

## Scene parameters
none
