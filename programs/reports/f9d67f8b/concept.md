# f9d67f8b

## Concept
- A picture that is mirror symmetric left to right and top to bottom has rectangles painted over it in one color; restore each covered cell from a mirror image of it that is still visible, and where both mirror images are covered or fall outside the grid, from its image across the diagonal.

## Scene
- `mirror-picture`: every cell whose image under the row mirror `r -> mirror_sum_v - r` or the column mirror `c -> mirror_sum_h - c` lies in the grid holds the color of that image, where neither cell is covered
- `tiled-picture`: the canvas cuts into `tile_count` × `tile_count` tiles, and `tile_sym` gives each tile the group of canvas mirrors and turns that holds on its cells: the mirrors across the canvas's center lines in every tile, and also its two diagonals in each tile with one coordinate in the band of rows and columns 8–23 and the other outside it
- `mask-recoverable`: each covered cell has an image, under a member of its tile's group, that is in the grid and not covered
- `covering-blocks`: some solid rectangles of `mask_color` lie over the picture, and the picture itself holds no `mask_color`

## Rules
- `uncovered-kept`: each cell not of `mask_color` keeps its color
- `restore`: each covered cell takes the color of its images, under the members of its tile's group, that are in the grid and not covered

## Parameters
- `mask_color`: 9
- `mirror_sum_v`: 31
    - the sum of a row and its mirror row
- `mirror_sum_h`: 31
    - the sum of a column and its mirror column

## Scene parameters
- `tile_sym`: a 4 × 4 table of groups, `SYM_D4` on tiles with one coordinate in the rows and columns 8–23 and the other outside them, and `SYM_BOX` elsewhere
    - the middle band of rows and columns; the cells with exactly one coordinate in it are symmetric across the main diagonal
