# d22278a0

## Concept
- Each corner seed draws nested L-shaped rings around its corner, one on every other step outward, and each cell goes to the seed nearest it; a cell equally near two seeds stays blank.

## Scene
- `square-grid`: the grid is square, filled with `background`.
- `corner-seeds`: a single non-background cell sits at each of two or more corners of the grid, each of its own color, and every other cell is `background`.

## Rules
- `nearest-seed`: each cell belongs to the seed at the least taxicab distance from it (the row distance plus the column distance); a cell at that least distance from two or more seeds belongs to no seed and is `background`.
- `alternating-rings`: a cell that belongs to a seed takes the seed's color when its Chebyshev distance from the seed (the larger of the row distance and the column distance) is a multiple of `ring_period`, and is `background` otherwise.

## Parameters
- `background`: 0
- `ring_period`: 2
    - the step between one ring of a seed and the next

## Scene parameters
none
