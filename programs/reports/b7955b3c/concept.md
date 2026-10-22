# b7955b3c

## Concept
- Solid rectangles lie stacked on a background, and plus-shaped marks are drawn over them; erase the marks, so each marked cell shows what the stack of rectangles shows there.

## Scene
- `layered-rectangles`: a background fills the frame, and solid axis-aligned rectangles, each of its own color, lie stacked over it; each rectangle hides the part of every lower rectangle that it covers.
- `visible-extent`: each rectangle shows cells on each of its four sides, so the bounding box of its visible cells, with the mark cells it lies under, is the rectangle.
- `marks`: marks of color `mark_color`, each of shape `mark_shape`, lie over the scene and hide the cells under them; no other cell has color `mark_color`.

## Rules
- `erase-marks`: each cell of color `mark_color` takes the color of the topmost rectangle that covers it, and the background color where no rectangle covers it; every other cell keeps its color.

## Parameters
- `mark_color`: 8

## Scene parameters
- `mark_shape`: the plus
    - a center cell and its four cardinal neighbors
