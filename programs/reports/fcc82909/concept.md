# fcc82909

## Concept
- Each small colored square gets a bar hanging below it, as wide as the square and as many rows tall as the square has different colors.

## Scene
- `background`: a field of `background`.
- `blocks`: a few `block_size`×`block_size` blocks of non-background cells, each cell any color other than `background` and `bar_color`, the blocks apart from one another.
- `room-below`: below each block, toward `direction`, the cells its bar covers are background and inside the grid.

## Rules
- `keep`: every input cell keeps its color.
- `bar`: under each block, toward `direction`, the cells in the block's columns from the row next to the block out to as many rows as the block has distinct colors take `bar_color`.

## Parameters
- `background`: 0
- `bar_color`: 3
- `direction`: down
    - the side of the block the bar hangs from

## Scene parameters
- `block_size`: 2
