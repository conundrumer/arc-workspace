# e73095fd

## Concept
- A wiring diagram of gray lines joins hollow gray boxes; fill the inside of every box with yellow, a box cut by the grid edge included.

## Scene
- `wire-network`: on a field of `background`, cells of `wire` form 1-wide straight lines and hollow rectangular box outlines; each line runs from a box side or the grid edge to a box side or the grid edge, and lines cross or join one another at junctions.
- `box-outline`: a box is a rectangular outline of `wire`, 1 cell thick, whose inside holds only `background`; each side ends at the box's corners, where no line continues the side, and a line meets a box only part way along a side.
- `clipped-box`: a box may run past the grid edge, and then the grid edge stands in for the sides and corners that lie off the grid.

## Rules
- `fill-box-inside`: each `background` cell inside a box becomes `fill`; every other cell keeps its color.

## Parameters
- `background`: 0
- `wire`: 5
    - the color of the lines and the box outlines
- `fill`: 4
    - the color the inside of a box takes

## Scene parameters
none
