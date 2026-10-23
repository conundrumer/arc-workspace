# e734a0e8

## Concept
- Lines cut the grid into equal tiles. One tile holds a drawing, and some other tiles hold a dot at their center. Each dotted tile gets a copy of the drawing.

## Scene
- `divider-tiling`: full rows and full columns of `divider_color`, each one cell wide, cut the grid into equal square tiles, with a tile at each end of each axis.
- `blank-tiles`: each tile is filled with `background_color`, apart from the cells the other scene claims name.
- `one-source`: exactly one tile, the source, holds cells of a color other than `background_color` and `divider_color`, and those cells all have one color, the drawing color.
- `center-markers`: each marked tile holds exactly one cell of `divider_color`, at the tile's center, and no other cell that is not `background_color`.
- `source-unmarked`: the source tile holds no cell of `divider_color`.

## Rules
- `stamp-marked`: each marked tile takes, at each cell, the color of the cell at the same place in the source tile.
- `keep-rest`: each other cell keeps its input color.

## Parameters
- `divider_color`: `0`
    - the color of the divider lines, and of the marker cell in a marked tile.
- `background_color`: `7`

## Scene parameters
- none
