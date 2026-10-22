# e50d258f

## Concept
- Several rectangular patches lie on a blank field; the output is the patch that holds the most cells of the counted color, cut out.

## Scene
- `rect-patches`: each input holds two or more solid rectangles of non-`background` cells on a field of `background`, and no two rectangles touch, diagonals included.
- `patch-palette`: every patch cell has a color of `palette`.
- `unique-max`: one patch holds strictly more cells of `count_color` than every other patch.

## Rules
- `pick-most`: the selected patch is the one with the most cells of `count_color`.
- `crop`: the output is the selected patch's bounding box, cell for cell.

## Parameters
- `background`: `0`
- `count_color`: `2`

## Scene parameters
- `palette`: `8`, `1`, `2`
