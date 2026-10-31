# ef26cbf6

## Concept
- Lines cut the grid into tiles set two deep; in each pair of tiles across the short side, one tile holds a single colored dot and the other a pattern, and the pattern is painted in the dot's color.

## Scene
- `divider-lines`: full rows or columns of `divider_color` cut the grid into equal 3×3 tiles laid out two deep on one axis and one or more long on the other.
- `tile-pairs`: each pair of tiles that share a line across the two-deep axis holds one key tile and one pattern tile.
- `key-tile`: a key tile holds exactly one cell other than `background`, at its center, of a color that is neither `pattern_color` nor `divider_color`.
- `pattern-tile`: a pattern tile holds only `background` and `pattern_color` cells, at least one of them `pattern_color`.
- `key-side`: every key tile sits on the same side of the two-deep axis.

## Rules
- `paint-pattern`: each `pattern_color` cell of a pattern tile takes the color of the key cell in the tile paired with it.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `pattern_color`: 1
    - the color of the cells that are recolored
- `divider_color`: 4
    - the color of the lines that cut the tiles
- `background`: 0

## Scene parameters
- none
