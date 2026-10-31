# f8be4b64

## Concept
- Each plus is a lamp that shines its center color along its row and its column across the grid, a hollow plus shining background; a beam stops at another plus's ring, never covers a ring cell, and where a row beam and a column beam cross the column beam shows.

## Scene
- `background`: every cell outside the pluses holds `background`.
- `pluses`: the input holds pluses, each four `ring_color` cells orthogonally around one center cell, whose color is not `ring_color`; the center of a hollow plus is `background`.
- `separate-pluses`: no two pluses share a cell or touch.
- `distinct-lines`: no two plus centers share a row or a column.
- `distinct-centers`: no two filled plus centers share a color.

## Rules
- `cast-cross`: each plus paints its center's row and column in its center color, from its center outward toward each of the four directions, a hollow plus painting `background`.
- `rings-kept`: every `ring_color` cell keeps its color.
- `blocked-at-ring`: a beam stops before the first `ring_color` cell it meets past its own plus's ring.
- `column-on-top`: where a beam along `top_axis` crosses a beam along the other axis, the `top_axis` beam's color shows.

## Parameters
- `ring_color`: 3
- `top_axis`: V
    - the axis whose beams show where two beams cross

## Scene parameters
- `background`: 0
