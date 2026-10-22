# dc2aa30b

## Concept
- The grid is a 3×3 board of small tiles, and the tiles are sorted by how many `counted_color` cells each holds: the tile with the fewest goes in the bottom-left slot, the next ones fill that row to the right, and then the rows above in turn, so the tile with the most ends at the top right.

## Scene
- `divider-board`: full rows and columns of `divider_color`, each one cell wide, cut the grid into `tile_count` × `tile_count` tiles of `tile_size` × `tile_size` cells.
- `two-color-tiles`: every tile cell is `counted_color` or `other_color`.
- `distinct-counts`: no two tiles hold the same number of `counted_color` cells.

## Rules
- `keep-dividers`: the divider lines stay where they are in the output.
- `rank-by-count`: each tile is ranked by its number of `counted_color` cells, from fewest to most.
- `place-by-rank`: the tile of each rank is copied whole, unchanged, into the slot of the same rank in the slot order, which starts at the `order_corner` slot and runs along `fill_axis` first, then steps to the next line of slots away from that corner.

## Parameters
- `divider_color`: 0
- `counted_color`: 1
- `order_corner`: bottom-left
    - the slot that takes the tile with the fewest `counted_color` cells
- `fill_axis`: horizontal
    - the axis the slot order runs along within one line of slots, before it steps to the next line

## Scene parameters
- `other_color`: 2
- `tile_count`: 3
    - the number of tiles along each axis
- `tile_size`: 3
    - the number of cells along each axis of a tile
