# da515329

## Concept
- The plus spins: each of its four arms keeps growing from its tip and curls into a spiral, and the four spirals wind around one another with a one-cell lane of background between walls, out past the edges of the grid.

## Scene
- `one-plus`: on a field of `background`, one plus of one color: four straight arms of one length, which leave the center cell `background` and point toward the four cardinal directions.

## Rules
- `arms-grow`: all four arms grow at once, one cell per step, from their tips, on an unbounded plane.
- `hug-the-spiral`: a growing arm keeps a lane of `corridor_width` background cells between its new cell and every wall cell it does not grow from, by the 8-neighborhood: it turns toward `sense` where it can, goes straight where it cannot, and turns the other way where straight is blocked.
- `clip`: the output has the input's size; a cell is the plus's color where a spiral passes through it, and `background` elsewhere, the center cell included.

## Parameters
- `background`: 0
- `sense`: clockwise
    - the sense in which each arm curls
- `corridor_width`: 1
    - the width of the background lane between two walls

## Scene parameters
- none
