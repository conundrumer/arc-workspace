# e9ac8c9e

## Concept
- Each gray square has a colored dot just off each of its four corners; the dots are removed, and each quarter of the square takes the color of the dot at its corner.

## Scene
- `field`: every cell outside the squares and the dots is `background`.
- `squares`: the input holds one or more solid squares of `block_color`, each with an even side.
- `corner-dots`: each square has, at each of its four corners, one cell diagonally adjacent to that corner and outside the square, which holds a color other than `background` and `block_color`.
- `apart`: no dot or square touches another square or another square's dots.

## Rules
- `erase-dots`: each corner dot becomes `background`.
- `quadrant-color`: each square is cut into four equal quarters, and every cell of a quarter takes the color of the dot at that quarter's corner of the square.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: `0`
- `block_color`: `5`

## Scene parameters
none
