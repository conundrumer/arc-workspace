# ac3e2b04

## Concept
- Some lines carry a marked crossing, a small square frame around one line cell. Through each mark, draw a line across the grid at right angles, and wherever that new line crosses another line, draw a 3×3 frame of the new color around the crossing.

## Scene
- `parallel-lines`: the input holds one or more straight lines of `line_color` on a field of `background`, each running the full length or width of the grid, all on one axis, with at least one background row or column between two lines.
- `marks`: at least one line carries a mark: a 3×3 frame of `mark_color` around one cell of that line, the center cell keeping `line_color`, the whole frame inside the grid and touching no other line.
- `one-mark-per-line`: a line carries at most one mark, and no two marks lie on one perpendicular line.

## Rules
- `cross-line`: through the center of each mark, a line of `draw_color` runs across the whole grid at right angles to the marked line, painting the background cells on it.
- `cross-frame`: where that new line crosses another line at a cell no mark surrounds, the eight cells around the crossing take `draw_color`, the crossing cell keeping `line_color`.
- `keep`: every other cell keeps its input color, the marks included.

## Parameters
- `line_color`: 2
- `mark_color`: 3
- `draw_color`: 1
    - the color of the drawn lines and frames
- `background`: 0

## Scene parameters
- none
