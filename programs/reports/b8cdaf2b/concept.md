# b8cdaf2b

## Concept
- A two-layer base sits on one edge of the grid; from the two outer corners of its top layer, a line in the color of the base's middle runs diagonally away from the base until it leaves the grid.

## Scene
- `background`: every cell outside the base is the `background` color.
- `base-row`: the line along the `base_side` edge is full: a middle run of one color (the inner color), flanked on both sides by runs of a second color (the outer color) of equal length.
- `cap-row`: the next line in from the `base_side` edge holds a run of the outer color exactly over the middle run of the base row, and the background everywhere else.
- `square-grid`: the grid is square.

## Rules
- `keep-input`: every cell off the rays keeps its input color.
- `cap`: the cap is the one run of non-background cells on the line next to the `base_side` edge, and the inner color is the one color of the base-line cells under it.
- `diagonal-rays`: from each end of the cap, a ray starts at the cell one step farther from the `base_side` edge and one step outward along the base, and runs on that diagonal, away from the base and outward, to the frame edge; each ray cell takes the inner color.

## Parameters
- `base_side`: bottom
    - the edge the base lies on
- `background`: 0

## Scene parameters
none
