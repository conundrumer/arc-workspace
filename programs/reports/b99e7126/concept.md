# b99e7126

## Concept
- A tiling of tiles mostly repeats one pattern; a few tiles carry a second pattern, and the shape its new color draws inside one tile is the shape the second-pattern tiles must make at the tile scale, so the output completes that shape.

## Scene
- `tiling`: divider lines of one color, one cell wide, cut the grid into a `tile_count` by `tile_count` tiling of `tile_size` by `tile_size` tiles, with a divider line along each edge of the grid.
- `base-tile`: most tiles hold one same two-color pattern, the base tile.
- `marked-tile`: every other tile holds one same pattern, the marked tile, made of one color of the base tile and one color that the base tile does not have, the new color.
- `partial-shape`: the marked tiles sit, at the tile scale, on cells of exactly one placement of the new color's shape in the tiling, and do not fill it.

## Rules
- `shape-of-new-color`: the shape is the set of cells of the marked tile whose color the base tile does not have, read as a `tile_size` by `tile_size` mask.
- `complete-shape`: the output keeps the input, and each tile at a cell of the one placement of the shape that holds the marked tiles becomes a marked tile.

## Parameters
- none

## Scene parameters
- `tile_size`: 3
- `tile_count`: 7
