# bf45cf4b

## Concept
- One shape is drawn in a single color, and a small patterned tile is drawn beside it; the output enlarges the shape so that each of its cells becomes a copy of the tile, and each empty cell of its bounding box becomes a tile-sized block of background.

## Scene
- `background`: one color fills most of the grid, and it surrounds two objects that do not touch each other.
- `mask-shape`: one object is in a single color, and its cells are connected through sides or corners.
- `pattern-tile`: the other object is a rectangle that holds two or more colors, and the background color can occur in its interior.

## Rules
- `block-per-mask-cell`: the output is the mask shape's bounding box, with each cell scaled up to a block the size of the tile.
- `tile-on-mask-cell`: a block whose cell belongs to the mask shape is a copy of the tile.
- `background-elsewhere`: a block whose cell does not belong to the mask shape is all background color.

## Parameters
- none

## Scene parameters
- none
