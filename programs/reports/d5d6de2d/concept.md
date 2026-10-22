# d5d6de2d

## Concept
- Each hollow box drawn in the outline color is replaced by its filled interior: the outline is erased, and the hole it encloses is painted in the fill color. A box with no hole leaves nothing.

## Scene
- `background-field`: every cell that no shape covers has the `background` color, and that color is the commonest one.
- `outline-shapes`: the shapes are separate rectangles in the `outline_color`, each a complete one-cell-wide border that encloses a rectangular hole of background, or a solid block too thin to hold a hole.
- `shapes-apart`: no two shapes touch, not even at a corner.

## Rules
- `fill-hole`: each `background` cell that no walk through `background` cells, from a cell to an edge neighbor, reaches from the frame edge takes the `fill_color`.
- `erase-rest`: every other cell, the outline cells included, takes the `background` color.

## Parameters
- `background`: 0
- `fill_color`: 3

## Scene parameters
- `outline_color`: 2
