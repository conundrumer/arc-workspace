# b7f8a4d8

## Concept
- A grid of framed squares, most of them filled with one color: the few squares filled with an odd color are joined to the other squares of that color in their row or column of squares by bridges of that color across the gaps.

## Scene
- `tiling`: on a field of `background`, a tiling of equal square tiles at one period on both axes, each a frame `frame-width` cells thick of one frame color around a solid interior of one color; the tiles at the right and bottom edges may be cut off.
- `common-interior`: one interior color, the commonest, fills most tiles.
- `odd-rectangle`: the tiles of each other interior color sit at the four corners of a rectangle of tiles: two tile rows by two tile columns.

## Rules
- `bridge-odd-tiles`: for each interior color other than the common one, between two tiles of that color in one tile row or one tile column, each `background` cell in line with their interiors becomes that color; the tiles between them stay as they are.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: 0

## Scene parameters
- `frame-width`: 1
