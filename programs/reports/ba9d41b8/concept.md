# ba9d41b8

## Concept
- Each solid rectangle keeps its one-cell outline, and its inside is punched with a checkerboard of `background` holes, counted from the rectangle's `anchor` corner.

## Scene
- `background-field`: every cell outside the rectangles is `background`.
- `solid-rectangles`: the input holds one or more filled rectangles, each of one color other than `background`, each at least 3 by 3, and no two of them touch.

## Rules
- `outline-kept`: each cell on a rectangle's outline keeps its color.
- `checker-holes`: an inside cell of a rectangle becomes `background` when the sum of its row and column distances from the rectangle's `anchor` corner has the parity `hole_parity`, and keeps its color otherwise.
- `rest-kept`: every cell outside the rectangles keeps its color.

## Parameters
- `background`: 0
    - the color of the field, and the color of the holes
- `anchor`: top-left
    - the corner of each rectangle from which the checkerboard's parity is counted
- `hole_parity`: 0
    - the parity, 0 for even and 1 for odd, of the distance sum at which a cell is a hole

## Scene parameters
- none
