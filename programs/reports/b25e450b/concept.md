# b25e450b

## Concept
- Each hole in a speckled field slides straight across the grid to the opposite edge, and it wipes its whole track clean as it goes.

## Scene
- `speckled-field`: the background is a mix of the two `field-colors`, with no pattern in where each color falls.
- `edge-blocks`: the cells of `block-color` form solid rectangles, each one touching exactly one edge of the grid and not reaching the opposite edge.
- `blocks-apart`: no two blocks touch, not even at a corner.

## Rules
- `cross-to-opposite`: each block moves to the opposite edge on the axis normal to the edge it touches, and it keeps its place on the other axis.
- `wipe-track`: each cell in the band the block's rows (for a block on a side edge) or columns (for a block on the top or bottom edge) span, from edge to edge, takes `trail-color`.
- `block-on-top`: a cell where a moved block lands takes `block-color`, also where it lies in the track of another block.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `block-color`: 0
- `trail-color`: 7
    - one of the two field colors

## Scene parameters
- `field-colors`: 5, 7
