# bc93ec48

## Concept
- The shape in each corner of the grid moves on to the next corner clockwise, and is drawn there over what is already in that corner.

## Scene
- `background-field`: the grid is a field of `background`, with one-color shapes on it.
- `corner-cells`: each corner cell is either `background` or a cell of a shape, and no shape holds two corner cells.

## Rules
- `corner-shape`: the shape of a corner is the 4-connected one-color component of non-`background` cells that holds the corner cell; a corner whose cell is `background` has no shape.
- `next-corner`: each corner's shape is copied to the next corner in the `sense` direction, translated with no turn or flip, so that its bounding box touches that corner's two edges.
- `overlay`: the copies are drawn over the input; each cell no copy covers keeps its input color, the cells of the shape that moved away included.

## Parameters
- `background`: 7
- `sense`: clockwise
    - the direction around the grid in which each corner's shape moves to the next corner

## Scene parameters
- none
