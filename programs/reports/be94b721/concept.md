# be94b721

## Concept
- Several colored shapes sit on a blank field; cut out the biggest one, the shape with the most cells.

## Scene
- `colored-shapes`: on a field of `background`, the input holds a few shapes, each a 4-connected group of cells of one color, no two of a color and no two touching.
- `one-biggest`: exactly one shape has more cells than every other shape.

## Rules
- `crop-biggest`: the output is the bounding box of the shape with the most cells, its cells in its color and every other cell of the box `background`.

## Parameters
- `background`: 0
    - the field color, which no shape takes and which fills the rest of the cropped box

## Scene parameters
none
