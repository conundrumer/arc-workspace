# e76a88a6

## Concept
- One multicolored pattern sits on the field, and each solid block of the placeholder color has the pattern's shape; the pattern is copied onto every placeholder block.

## Scene
- `field`: the cells of color `background` form the field.
- `one-pattern`: one object, a 4-connected set of non-field cells that holds no `placeholder` cell, is the pattern; its cells fill its bounding box and take more than one color.
- `placeholder-blocks`: every other object is a solid block of color `placeholder` whose bounding box has the extent of the pattern's bounding box.

## Rules
- `stamp-pattern`: each cell of a placeholder object takes the color of the cell at the same place in the pattern's bounding box; every other cell keeps its input color.

## Parameters
- `placeholder`: 5
    - the color of the blocks that the pattern replaces
- `background`: 0

## Scene parameters
none
