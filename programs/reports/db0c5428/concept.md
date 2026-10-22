# db0c5428

## Concept
- A 3×3 arrangement of blocks with an empty center block grows outward to a 5×5 arrangement: each outer block is copied across the center to the block place two steps away on the far side, and the empty center fills with a shrunken copy of the frame of cells around it.

## Scene
- `one-square`: on a field of color `background`, one square of side 3 × `block`, which holds no `background` cell outside its center block.
- `block-grid`: the square divides into 3×3 blocks of side `block`, and its center block (the hole) is all `background`.
- `d4-symmetric`: the square is unchanged under each element of D4.
- `room`: the square stands at least `block` cells from each edge of the grid.

## Rules
- `keep-square`: the eight outer blocks of the square stay as they are.
- `copy-across`: for each of the eight directions d, a copy of the block at -d from the hole, unturned, is drawn at the block place 2d from the hole.
- `fill-hole`: each hole cell at offset d from the hole's center cell takes the color of the input cell at offset 2d from that center, and the center cell takes the color of the frame cells at offsets (±1, ±2) and (±2, ±1).
- `rest-background`: every other cell is `background`.

## Parameters
- `background`: 8

## Scene parameters
- `block`: 3
