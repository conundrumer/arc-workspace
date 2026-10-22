# ad173014

## Concept
- Boxes sit on a closed loop, each holding a colored shape; every shape keeps its form and takes the color of the shape in the next box along the loop, so the colors turn one step around the loop.

## Scene
- `loop`: a closed rectangular loop of `line_color`, one cell wide, on a field of `background`.
- `boxes-on-loop`: three or more boxes, each a square outline of `frame_color`, that the loop passes through; no two boxes touch.
- `one-shape-per-box`: each box's interior holds one shape of a single color on `background`, and the shapes of different boxes have different colors.

## Rules
- `color-turn`: each shape keeps its cells and takes the color of the shape in the box that comes next along the loop in `sense`.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `sense`: clockwise
    - the direction around the loop in which a box finds the box whose color it takes.

## Scene parameters
- `background`: 0
- `line_color`: 1
- `frame_color`: 2
