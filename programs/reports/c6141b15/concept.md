# c6141b15

## Concept
- A line and some copies of a shape swap places: a copy of the shape goes on each end of the line, and lines in the line's color join the shape centers.

## Scene
- `background`: a field of `bg`.
- `one-line`: one straight run of cells of one color along a row, a column, or a diagonal, at least two cells long.
- `shape-copies`: two or more identical copies of one shape in a second color, each one 8-connected object whose bounding box has odd extents, so that it has a center cell.
- `aligned-centers`: each two shape centers lie on one row, column, or diagonal.
- `apart`: the line and the copies are separate objects that do not touch, even at a corner.

## Rules
- `stamps-at-line-ends`: a copy of the shape, in the shape's color, sits with its center on each of the line's two end cells.
- `lines-join-centers`: a straight run of the line's color joins each two shape centers, along the row, column, or diagonal they share, end cells included.
- `rest-background`: every other cell is `bg`; the input line and copies do not stay.

## Parameters
- `bg`: 7
    - the background color

## Scene parameters
- none
