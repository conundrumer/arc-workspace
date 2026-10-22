# ddf7fa4f

## Concept
- A row of single colored markers sits along the top edge, and each gray block below takes the color of the marker that stands above it in one of its columns.

## Scene
- `marker-line`: the line of cells at the `marker-edge` holds the markers, single cells of colors other than `bg` and `block-color`, with `bg` between them; the line next to it holds only `bg`.
- `blocks`: the rest of the grid holds solid rectangles of `block-color` on `bg`, each one 4-connected component; two blocks can touch at a corner.
- `one-marker-per-block`: the span of each block along the marker line holds exactly one marker, and each marker stands over exactly one block.
- `marker-count`: the marker line holds `marker-count` markers.

## Rules
- `recolor-by-marker`: each block cell takes the color of the marker whose cell on the marker line falls in the block's span along that line.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `marker-edge`: top
    - the edge whose line holds the markers; the blocks' spans are read along that line
- `block-color`: 5
- `bg`: 0

## Scene parameters
- `marker-count`: 3
