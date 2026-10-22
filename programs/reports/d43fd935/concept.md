# d43fd935

## Concept
- Each dot that lies level with the block, in a row or a column the block spans, shoots a line of its own color toward the block until the line touches it.

## Scene
- `one-block`: a background of color `background` holds one solid 2×2 block of color `block_color`.
- `single-dots`: every other non-background cell is a single cell of a color other than `block_color`, and no two of them share an edge.
- `clear-paths`: between a dot that is level with the block and the block, every cell is background.

## Rules
- `ray-to-block`: a dot that shares a row or a column with a cell of the block paints every cell between it and the block, on that row or column, in the dot's color.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `block_color`: 3

## Scene parameters
- `block_size`: 2×2
