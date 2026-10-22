# d89b689b

## Concept
- Four marker cells sit around a 2×2 block, one off each corner; each marker moves into the block cell at its corner, and everything else is cleared.

## Scene
- `one-block`: the grid holds one 2×2 block of color `block_color` on a field of `background`.
- `four-markers`: besides the block, the grid holds exactly four single cells, each of a color other than `background` and `block_color`.
- `one-marker-per-corner`: each marker lies strictly above or strictly below the block's rows, and strictly left or strictly right of its columns, and each of the block's four diagonal corners has exactly one marker.

## Rules
- `marker-to-corner`: each block cell takes the color of the marker off the block corner that cell sits at.
- `clear-rest`: every other cell of the output is `background`, so the markers leave their places.

## Parameters
- `background`: 0
- `block_color`: 8
    - the color of the block whose cells the markers replace

## Scene parameters
- none
