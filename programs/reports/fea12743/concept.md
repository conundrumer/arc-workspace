# fea12743

## Concept
- Six small drawings sit in a grid; one of them is exactly two of the others laid on top of each other. Paint the two pieces one color and the drawing they make together another; where a piece is drawn twice, paint the first copy in reading order.

## Scene
- `tile-layout`: the grid is a `tile_rows` by `tile_cols` layout of `tile_size` square tiles, with a `gutter`-wide background border around and between them.
- `one-ink`: every tile is drawn in `ink` on `background`; nothing else is drawn.
- `one-union`: exactly one tile is the cell-wise union of two other tiles, and the two shapes it is the union of are one pair of shapes, though a shape of the pair may be drawn in more than one tile.

## Rules
- `paint-parts`: for each of the two shapes whose union is another tile, the first tile in `copy_order` that holds that shape, other than the union tile, has its ink recolored `part_color`.
- `paint-union`: the tile that is that union has its ink recolored `union_color`.
- `keep-rest`: every other cell is copied from the input.

## Parameters
- `part_color`: 8
- `union_color`: 3
- `copy_order`: reading order, rows from the top, each row from the left
    - the order of tiles in which the first copy of a duplicated part shape is the one painted
- `background`: 0
- `tile_size`: 4
- `gutter`: 1
    - the width of the background border around and between the tiles

## Scene parameters
- `ink`: 2
- `tile_rows`: 3
- `tile_cols`: 2
