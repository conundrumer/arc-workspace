# b6afb2da

## Concept
- Each solid gray rectangle becomes a framed box: its corners turn one color, the rest of its border another, and its inside a third.

## Scene
- `background`: every cell outside the rectangles is the background color `background`.
- `solid-rectangles`: the other cells form solid rectangles of the color `shape`, each at least 3 cells on each side, no two touching.

## Rules
- `corner`: each corner cell of a rectangle of `shape` cells takes `corner_color`.
- `edge`: each other cell on a rectangle's border takes `edge_color`.
- `interior`: each cell inside a rectangle's border takes `interior_color`.
- `keep-background`: each background cell stays as it is.

## Parameters
- `corner_color`: 1
- `edge_color`: 4
- `interior_color`: 2
- `shape`: 5
    - the color of the rectangles' cells, which the rules recolor

## Scene parameters
- `background`: 0
