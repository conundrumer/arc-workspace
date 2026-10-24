# fc10701f

## Concept
- The `mover` block slides straight along its corridor onto the `target` block and takes its place; every gate it slides through, a pair of `gate` marks on the two sides of the corridor, is stamped with `mark` where the block passed between them.

## Scene
- `two-blocks`: the grid is `background` with one solid `mover` block and one solid `target` block of the same size, aligned so that they span the same rows or the same columns.
- `corridor`: the corridor is the cells strictly between the two blocks along the axis that joins them, across the blocks' common span; it holds only `background`.
- `gates`: `gate` cells stand in mirrored pairs on the two sides of the corridor's span, against it, some along the corridor and some elsewhere.

## Rules
- `vacate`: the `mover` block's cells become `background`.
- `land`: the `target` block's cells become `mover`.
- `stamp-gates`: each corridor cell that has a `gate` cell on each side of it, in its line across the corridor's axis, becomes `mark`.
- `keep`: every other cell keeps its input color.

## Parameters
- `mover`: 7
    - the color of the block that moves
- `target`: 9
    - the color of the block it lands on
- `gate`: 0
- `mark`: 2
    - the color a passed gate's corridor cells take
- `background`: 6
    - the color the vacated cells take

## Scene parameters
- none
