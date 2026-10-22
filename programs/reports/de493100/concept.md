# de493100

## Concept
- A picture has the mirror symmetry of a square, and a solid block of one color covers part of it; the output is what the block hides, filled in from the mirror images of the hidden cells.

## Scene
- `square-picture`: the grid shows the top-left part of a square picture of side `picture_size`, which the grid crops at its bottom and right edges.
- `tiled-picture`: the picture cuts into `tile_size` × `tile_size` tiles, and each tile of one quarter of the picture, with its images in the other quarters, carries the group of the picture's mirrors and turns that `tile_groups` gives it.
    - `side-mirrors`: every tile's group holds the mirrors across the picture's vertical and horizontal center lines.
    - `diagonal-mirrors`: a tile off the quarter's diagonal also holds the mirrors across the picture's two diagonals.
- `mask-block`: one solid rectangle of `mask_color` covers part of the picture, and `mask_color` occurs nowhere else.
- `mask-recoverable`: each masked cell has an image, under a member of its tile's group, that is in the grid and outside the mask.

## Rules
- `crop-to-mask`: the output is the mask's bounding box.
- `fill-from-mirror`: each output cell takes the color of an image of its masked cell, under a member of its tile's group, that is in the grid and outside the mask.

## Parameters
- `mask_color`: 7
- `picture_size`: 32
    - row r mirrors to row 31−r, and col c to col 31−c, so the grid leaves out the picture's last two rows and cols.
- `tile_size`: 8
- `tile_groups`: tile (0,0) `SYM_BOX`, tile (0,1) `SYM_D4`, tile (1,0) `SYM_D4`, tile (1,1) `SYM_BOX`
    - keyed by a tile's (row, col) among the 2 × 2 tiles of the top-left quarter; the evidence's inputs, with the mask left out, determine each group as the members that hold on the tile in every input.

## Scene parameters
- none
