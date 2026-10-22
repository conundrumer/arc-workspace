# c61be7dc

## Concept
- Two parallel walls squeeze a shape that sits between them: the walls close in until the gap is one cell wide, and the shape is pressed into a line of the same number of cells along that gap, centered where the cross line crosses it.

## Scene
- `field`: every cell that is not a line or the shape has color `background`.
- `walls`: two full lines of color `line_color`, parallel to each other, bound a corridor whose width is odd and at least 3.
- `cross-line`: one line of color `line_color`, perpendicular to the walls, runs from edge to edge outside the corridor, and inside the corridor the input shows only shape or `background` on it.
- `shape`: the cells of color `shape_color` all lie in the corridor, are symmetric about the cross line, and are odd in number.

## Rules
- `close-walls`: each wall moves to the line next to the corridor's center line, and the cells of the old walls take `background`, except where the cross line passes.
- `press-shape`: the shape becomes a line of `shape_color` on the corridor's center line, with as many cells as the shape has, centered on the cross line; every other cell of the old corridor that no wall or cross line takes is `background`.
- `restore-cross-line`: the cross line runs from edge to edge in the output, across the old corridor too, and the shape's line covers it at the one cell where they meet.

## Parameters
- `background`: 7
- `line_color`: 0
    - the color of the walls and the cross line
- `shape_color`: 5

## Scene parameters
- none
