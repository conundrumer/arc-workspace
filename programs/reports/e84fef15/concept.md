# e84fef15

## Concept
- The grid is a lattice of copies of one tile, and one copy has lost some of its marks; output the tile, with each cell where that copy differs from the others painted in `fill`.

## Scene
- `divided-grid`: full lines of `divider` cut the grid into equal square tiles, with one line between each two tiles on each axis.
- `repeated-tile`: every tile but one holds the same pattern of marks on a field of `background`.
- `damaged-tile`: one tile differs from the pattern, and each cell where it differs is a mark of the pattern that is `background` in that tile.

## Rules
- `output-tile`: the output is the pattern, at the size of one tile.
- `mark-lost`: each cell where the damaged tile differs from the pattern takes `fill`.

## Parameters
- `fill`: 1
    - the color of a lost mark in the output
- `divider`: 3

## Scene parameters
- `background`: 8
