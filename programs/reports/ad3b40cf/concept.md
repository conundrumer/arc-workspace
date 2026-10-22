# ad3b40cf

## Concept
- A line splits a square grid into two mirror halves, and the shapes of the rarer of the two shape colors get a mirror copy on the empty half.

## Scene
- `square-grid`: the grid is square.
- `mirror-line`: a straight line of color `line` runs edge to edge along one of the grid's own symmetry axes: the middle row, the middle column, or a corner-to-corner diagonal.
- `one-side`: every cell that is neither `background` nor `line` lies on one side of the line, and the other side is all `background`.
- `two-colors`: those cells, the shapes, take exactly two colors, and the two colors have different cell counts.

## Rules
- `mirror-rarer`: each cell of the shape color with the fewest cells is copied to its mirror image across the line, over whatever that image cell holds; every other cell keeps its input color.

## Parameters
- `background`: 8
- `line`: 1
    - the color of the mirror line

## Scene parameters
none
