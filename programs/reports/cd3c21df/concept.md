# cd3c21df

## Concept
- Several objects lie on a background, and every object but one has an exact copy elsewhere in the grid; the output is the one object with no copy, cropped to its box.

## Scene
- `objects-on-background`: the input holds objects, each a 4-connected group of cells not of color `background`, and no two objects touch, even at a corner.
- `one-unique-object`: exactly one object has no other object of the same shape and colors, up to translation.
- `others-repeat`: each other object has at least one other object of the same shape and colors, up to translation.

## Rules
- `crop-unique`: the output is the bounding box of the unique object, with its cells in their colors and the other cells of the box in color `background`.

## Parameters
- `background`: 0

## Scene parameters
none
