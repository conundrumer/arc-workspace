# e9614598

## Concept
- Two marks sit on one row or one column; draw a small plus exactly halfway between them.

## Scene
- `background`: every cell other than the marks holds `background`.
- `two-marks`: the input holds exactly two non-background cells, both of `mark_color`.
- `marks-aligned`: the two marks share a row or a column.
- `even-separation`: the distance between the two marks along their line is even, so one cell lies equally far from each.
- `plus-clear`: the plus drawn at that cell lies inside the grid and covers no mark.

## Rules
- `keep-input`: every input cell is kept, except where the plus is drawn.
- `midpoint`: the center is the cell on the line between the two marks at equal distance from each.
- `plus`: the center and each cell `arm_length` or fewer steps from it in each of the four cardinal directions take `plus_color`.

## Parameters
- `plus_color`: 3
- `arm_length`: 1
    - the number of cells each arm of the plus reaches from the center
- `background`: 0

## Scene parameters
- `mark_color`: 1
