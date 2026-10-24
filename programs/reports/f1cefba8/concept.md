# f1cefba8

## Concept
- A filled rectangle sits inside a thicker frame of another color, with a few one-cell nubs of the inner color poking out into the frame; each nub marks a line, which cuts through the inner rectangle in the frame color and shoots out past the frame to the grid edges in the inner color.

## Scene
- `framed-rectangle`: one solid rectangle of a frame color on the `background`, with a solid rectangle of a second, inner color inside it, inset from every side of the frame by `frame-width` cells.
- `nubs`: a few single cells of the inner color in the frame ring, each 4-adjacent to the inner rectangle's side, and so one cell outside that side, at the inner rectangle's span on the other axis.
- `one-nub-per-line`: no two nubs lie on one row or one column.

## Rules
- `nub-erased`: each nub takes the frame color.
- `line-through-inner`: each cell of the inner rectangle on the row of a nub on the left or right side, or on the column of a nub on the top or bottom side, takes the frame color.
- `line-outside`: each `background` cell on such a row or column takes the inner color, on both sides of the frame out to the grid edge.
- `rest-kept`: every other cell keeps its color, the frame ring included.

## Parameters
- `background`: 0

## Scene parameters
- `frame-width`: 2
    - the thickness of the frame ring around the inner rectangle on each side
