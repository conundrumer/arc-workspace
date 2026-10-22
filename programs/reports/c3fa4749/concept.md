# c3fa4749

## Concept
- Solid blocks sit in a field of random colors, and a channel of scribble runs into each block from the grid border; a channel that is a dead end fills with the color at its mouth, and a channel that leaks out elsewhere stays as it is.

## Scene
- `noise-field`: the grid is a field of random colors.
- `blocks`: several solid one-color blocks lie in the field against the grid border; a block is made of one-color 4-connected regions of at least `min_block_cells` cells each, and a channel that crosses a block cuts it into more than one such region.
- `channels`: each block holds one or more pockets, each a 4-connected set of cells that lie in no block region.

## Rules
- `dead-end-fills`: a pocket whose every neighbor in the grid lies in one block region, and that meets the grid border at exactly one cell, takes that cell's color in every cell, the block-colored cells it walls in included.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `min_block_cells`: 10
    - the fewest cells a one-color 4-connected region has to be a block

## Scene parameters
none
