# c64f1187

## Concept
- A legend pairs each color with a small shape, and a grid of gray tiles marks a color in some tiles: each marked tile becomes the shape of its color, drawn in that color, each unmarked tile becomes empty, and the output is the tile grid alone.

## Scene
- `legend`: a row of entries, each a marker cell of its own color with a shape of `shape_color` drawn in the tile-sized box whose `marker_corner` the marker touches diagonally from outside.
- `tile-grid`: a rectangular grid of `tile_size` tiles of `tile_color`, apart from the legend, with a `gap`-wide line of background between neighboring tiles.
- `code`: a tile holds at most one cell of another color, at its `code_corner`, and that color is the color of a legend marker.
- `background`: every other cell is `background`.

## Rules
- `crop-to-tiles`: the output is the bounding box of the tile grid, and the gaps stay background.
- `stamp-shape`: a tile with a code takes the legend shape of the code's color, each shape cell at the same place in the tile as in its legend box, in the code's color, and the tile's other cells become background.
- `blank-tile`: a tile with no code becomes background.

## Parameters
- `tile_color`: 5
- `shape_color`: 1
- `background`: 0
- `marker_corner`: top-left
    - the corner of a legend box that the marker touches diagonally from outside

## Scene parameters
- `tile_size`: 2 by 2
- `gap`: 1
- `code_corner`: bottom-right
