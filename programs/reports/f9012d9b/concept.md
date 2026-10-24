# f9012d9b

## Concept
- A repeating tile pattern covers the grid except for a patch blanked out in `hole_color`; the output is the missing piece, the pattern's content that belongs under the patch.

## Scene
- `periodic-pattern`: every cell outside the patch belongs to a pattern that repeats with one period along the rows and one along the columns, each period shorter than the grid on its axis.
- `one-rectangular-hole`: the cells of `hole_color` form one solid rectangle, and no other cell has that color.

## Rules
- `least-period`: the periods are the least pair, the row period first, at which every two non-hole cells whose row distance is a multiple of the row period and whose column distance is a multiple of the column period hold one color.
- `fill-from-period`: each hole cell takes the color of a non-hole cell at a distance from it that is a multiple of the period on each axis.
- `crop-to-hole`: the output is the hole's rectangle, filled, cut out of the grid.

## Parameters
- `hole_color`: 0
    - the color that marks the blanked-out cells

## Scene parameters
none
