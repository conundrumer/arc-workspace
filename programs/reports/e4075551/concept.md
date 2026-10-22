# e4075551

## Concept
- Four dots mark the four sides of a rectangle, and a fifth dot marks a point inside it: draw the rectangle with each side in its dot's color, and draw a cross through the inner point that spans the rectangle's interior.

## Scene
- `five-dots`: on a field of `background`, the input holds exactly five single non-background cells, with no two of them adjacent.
- `center-dot`: exactly one of the five cells has the color `center_color`.
- `side-dots`: each of the other four cells is the unique cell of the five that is extreme toward one side (topmost, bottommost, leftmost, rightmost), and each side has exactly one such cell.
- `inside`: the center dot lies strictly inside the box whose edges are the rows of the top and bottom dots and the columns of the left and right dots, and each side dot lies on that box's edge between the box's two corners on that edge.

## Rules
- `frame`: the output draws the outline of that box, each side in the color of its side dot; the two edges on `corner_axis` (top and bottom) include the corners, and the two other edges (left and right) run only between them.
- `cross`: inside the box, the row and the column through the center dot take `cross_color`, from edge to edge of the box's interior.
- `center-kept`: the center dot keeps `center_color`.
- `rest-background`: every other cell is `background`; the side dots' input cells are not kept apart from where the frame covers them.

## Parameters
- `center_color`: 2
- `cross_color`: 5
- `corner_axis`: vertical
    - the axis whose two edges (top and bottom) take the box's corner cells.
- `background`: 0

## Scene parameters
- none
