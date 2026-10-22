# bd5af378

## Concept
- An L-shaped line along two edges of the grid steps one cell inward along the diagonal. The cells it leaves take the field color, and the rest of the field turns 8. A diagonal of the field color runs from the L's corner into the field, and the two corner cells of the L, the old one and the new one, are 8.

## Scene
- `field`: the grid is filled with one field color, except for the L.
- `l-line`: the L is one full row and one full column of a second color, `l_width` cells thick, along the two edges that meet at one corner of the grid.

## Rules
- `edge-to-field`: the cells at distance less than `shift` from either edge of the L's corner take the field color.
- `l-steps-in`: the cells at distance `shift` from one edge of the corner, and at least `shift` from the other, take the L's color.
- `field-to-fill`: the cells at distance more than `shift` from both edges of the corner take `fill_color`.
- `corner-diagonal`: on the corner's diagonal, the cells at distance at most `shift` from the corner take `fill_color`, and the cells farther out take the field color.

## Parameters
- `shift`: 1
    - how many cells the L steps inward
- `fill_color`: 8
    - the color the field turns, and the color of the L's corner cells

## Scene parameters
- `l_width`: 1
