# b2bc3ffd

## Concept
- Each object standing on the floor jumps away from the floor by as many cells as it has.

## Scene
- `floor`: a full line of `floor_color` lies along the `floor_side` edge of the grid.
- `background`: every cell that is neither floor nor object is `background`.
- `objects`: the objects are 4-connected single-color components of the cells that are neither `background` nor `floor_color`, and each object has a different color.
- `grounded`: each object touches the line next to the floor.
- `fits`: each object, moved away from the floor by its cell count, stays inside the grid.

## Rules
- `jump`: each object moves away from the floor by a distance equal to its cell count, and keeps its shape and color.
- `clear`: the cells an object left, and that no moved object covers, become `background`.
- `keep-floor`: the floor stays as it is.

## Parameters
- `background`: 7
- `floor_color`: 8
- `floor_side`: bottom
    - the edge the floor lies along; the objects move toward the opposite edge.

## Scene parameters
none
