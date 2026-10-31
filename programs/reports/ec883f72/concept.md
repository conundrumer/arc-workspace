# ec883f72

## Concept
- A solid block sits in a walled-off corner pocket. From each bend of the wall, a diagonal beam in the block's color shoots out, away from the block, to the edge of the grid.

## Scene
- `background`: every cell outside the two objects is `background`.
- `core`: one solid rectangle of one color, the core.
- `wall`: one 1-wide wall of another color, made of straight arms that meet at right-angle bends. Each free end of an arm reaches the grid edge, and together with the grid edge the wall encloses the core.
- `wall-gap`: a background band `gap` cells wide separates the core from each wall arm that faces it.

## Rules
- `keep-input`: the output starts as a copy of the input.
- `corner-rays`: at each bend of the wall (a wall cell with wall neighbors on two perpendicular sides), a diagonal ray in the core's color starts at the diagonal neighbor that points away from both of those neighbors, and continues in that direction to the grid edge.

## Parameters
- `background`: 0

## Scene parameters
- `gap`: 1
    - the width of the background band between the core and the wall
