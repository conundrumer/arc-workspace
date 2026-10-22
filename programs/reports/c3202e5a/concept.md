# c3202e5a

## Concept
- Lines cut the grid into equal tiles of scattered colored marks; output the one tile whose marks are all one color.

## Scene
- `divider-lattice`: full rows and full columns of one color, evenly spaced, cut the grid into equal square tiles, with no line on the grid's edge.
- `one-mono-tile`: exactly one tile has marks of a single color; every other tile has marks of two or more colors.

## Rules
- `crop-mono-tile`: the output is the mono-color tile, cropped to the tile's cells, with its marks and its `background` cells as they are.

## Parameters
- `background`: 0

## Scene parameters
none
