# bf32578f

## Concept
- A shape is half of a closed outline; mirror it across its open side to close the outline, then keep only the inside, filled in the shape's color.

## Scene
- `one-shape`: the input holds one shape of one color on a field of `bg`.
- `half-outline`: the shape is an open curve whose two ends lie in its column nearest `mirror-dir`, so that it opens toward `mirror-dir`.
- `room`: the grid has room for the shape's mirror image on its `mirror-dir` side.

## Rules
- `mirror`: the shape and its mirror image, across the line just past the shape's edge toward `mirror-dir`, form one closed outline.
- `fill-inside`: each cell the closed outline encloses takes the shape's color, and every other cell, the outline included, is `bg`.

## Parameters
- `bg`: 0
- `mirror-dir`: R
    - the direction the shape opens toward, in which its mirror image lies

## Scene parameters
- none
