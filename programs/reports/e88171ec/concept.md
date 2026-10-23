# e88171ec

## Concept
- A noisy field hides one large empty rectangle; paint that rectangle's inside, one cell in from its edge, in a new color.

## Scene
- `noise-field`: the grid is a random scatter of the hole color and one or more other colors.
- `one-largest-hole`: one rectangle made only of `hole_color` cells has a larger area than every other such rectangle, and it is at least 3 cells on each axis.

## Rules
- `copy-input`: every cell keeps its input color, except those the next rule paints.
- `fill-inset`: the cells of the largest `hole_color` rectangle that are `margin` or more cells in from each of its edges take `fill_color`.

## Parameters
- `hole_color`: 0
- `fill_color`: 8
- `margin`: 1
    - the width of the rectangle's edge band that keeps `hole_color`

## Scene parameters
none
