# f9d67f8b

## Concept
- A picture that is mirror symmetric left to right and top to bottom has rectangles painted over it in one color; restore each covered cell from a mirror image of it that is still visible, and where both mirror images are covered or fall outside the grid, from its image across the diagonal.

## Scene
- `mirror-picture`: every cell whose image under the row mirror `r -> mirror_sum_v - r` or the column mirror `c -> mirror_sum_h - c` lies in the grid holds the color of that image, where neither cell is covered
- `diagonal-picture`: every cell with one coordinate in the band `diag_band` and the other outside it holds the color of its image across the main diagonal `(r, c) -> (c, r)`, where neither is covered; the picture inside the band on both coordinates is not diagonal symmetric
- `covering-blocks`: some solid rectangles of `mask_color` lie over the picture, and the picture itself holds no `mask_color`

## Rules
- `uncovered-kept`: each cell not of `mask_color` keeps its color
- `mirror-restore`: each covered cell takes the color that its row-mirror, column-mirror and half-turn images share, of those that are in the grid and not covered
- `diagonal-restore`: a covered cell with no such image takes the color that its image across the diagonal through the mirror center and that image's mirror images share, of those visible

## Parameters
- `mask_color`: 9
- `mirror_sum_v`: 31
    - the sum of a row and its mirror row
- `mirror_sum_h`: 31
    - the sum of a column and its mirror column

## Scene parameters
- `diag_band`: rows and columns 8–23
    - the middle band of rows and columns; the cells with exactly one coordinate in it are symmetric across the main diagonal
