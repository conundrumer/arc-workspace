# d94c3b52

## Concept
- The grid is a lattice of small tiles, each holding a shape. One tile is drawn in the key color. Every tile with the key's shape takes the key color, and every tile that lies between two key-shape tiles in one lattice row or column takes the link color.

## Scene
- `tile-lattice`: the grid is a lattice of `tile_size`×`tile_size` tiles, separated from each other and from the frame edge by lines of `gap` background cells, `lattice_rows` tiles down and `lattice_cols` tiles across.
- `shape-tiles`: every tile but one holds a shape in `shape_color` on background, and a shape may be as small as one cell.
- `one-key-tile`: one tile holds its shape in `key_color` and no `shape_color` cell.
- `key-shape-repeats`: at least one other tile holds the same shape as the key tile, at the same cells of the tile.

## Rules
- `match-takes-key-color`: each tile whose shape equals the key tile's shape, cell for cell with no rotation or reflection, recolors its shape cells (its non-background cells) to `key_color`.
- `between-takes-link-color`: each tile that lies strictly between two key-shape tiles (the key tile included) in one lattice row or one lattice column, and is not a key-shape tile itself, recolors its shape cells to `link_color`.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `tile_size`: 3
- `gap`: 1
    - the width of the background lines between tiles and at the frame edge
- `key_color`: 8
- `link_color`: 7
- `background`: 0

## Scene parameters
- `shape_color`: 1
- `lattice_rows`: 4
- `lattice_cols`: 6
