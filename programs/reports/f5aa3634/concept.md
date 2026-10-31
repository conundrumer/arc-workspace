# f5aa3634

## Concept
- Several small multicolored objects are scattered on the background, and exactly one of them appears twice, identical in shape and colors; the output is that repeated object, cropped to its bounding box.

## Scene
- `scattered-objects`: on a field of `background`, the non-background cells form separate objects, each a connected group of cells of several colors, with background between any two objects.
- `one-repeated-object`: exactly one object occurs twice, with the same cells and the same color at each cell up to translation; every other object occurs once.

## Rules
- `crop-repeated`: the output is the bounding box of the repeated object, with each of its cells in its color and every other cell of the box `background`.

## Parameters
- `background`: 0
    - the color of the field, which is not part of any object and fills the output box around the object

## Scene parameters
- none
