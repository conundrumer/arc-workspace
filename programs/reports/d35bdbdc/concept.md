# d35bdbdc

## Concept
- A wire of `wire_color` links two boxes: each of its two ends stops next to the middle cell of one side of a box. Each linked box looks up the box whose outer color is its own center color, and takes that box's center color. Every other box is erased.

## Scene
- `boxes`: separate shapes on a field of `background`, each a 3×3 ring or a plus of 5 cells around one center cell, and possibly cut off by the grid edge; the outer cells of a box are one color, and no two boxes have the same outer color.
- `wire`: one line of `wire_color`, of cells joined at sides or corners, that overlaps no box and has two ends; each end is next to (4-adjacent) the middle cell of one side of a box.
- `unhooked-ends`: each end of the wire has one neighbor in the wire, where two wire cells that touch at a corner are neighbors only when no wire cell touches both of them by a side

## Rules
- `linked-boxes`: a box is linked when a wire end is next to the middle cell of one of its sides, and its center color is the outer color of another box.
- `center-lookup`: a linked box's center takes the center color of the box whose outer color equals the linked box's center color.
- `erase-others`: every cell of a box that is not linked becomes `background`.
- `keep-rest`: the wire and the outer cells of the linked boxes stay as they are.

## Parameters
- `background`: 0
- `wire_color`: 5

## Scene parameters
- `box_extent`: 3
    - the side of each box's bounding square
