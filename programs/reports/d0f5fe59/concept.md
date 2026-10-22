# d0f5fe59

## Concept
- Count the shapes in the picture, and draw that count as a diagonal line of marks in a square grid whose side is the count.

## Scene
- `shapes-on-background`: a field of color `background` with one or more shapes, each a group of non-background cells joined through sides or corners.
- `one-shape-color`: every shape is of one color, the shape color.

## Rules
- `square-of-count`: the output is an N×N grid, where N is the number of shapes.
- `diagonal-marks`: the output cells on the `diagonal` of the square take the shape color, and every other cell takes `background`.

## Parameters
- `background`: 0
- `diagonal`: the main diagonal, from the top-left corner to the bottom-right corner

## Scene parameters
- none
