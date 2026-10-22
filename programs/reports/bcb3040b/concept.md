# bcb3040b

## Concept
- Two marker cells lie on one straight line across a noisy grid; connect them with a line, and where the line crosses a noise mark, give it a second color.

## Scene
- `noise-field`: every cell other than the markers is one of the field colors `field_colors`.
- `two-markers`: exactly two cells have the color `marker_color`.
- `markers-aligned`: the two markers lie on one row, one column, or one diagonal.
- `markers-on-opposite-edges`: the two markers sit on opposite edges of the grid, so the segment between them spans the grid.

## Rules
- `draw-segment`: each cell strictly between the two markers on their common line is recolored by `line_paint`, keyed by its input color.
- `keep-rest`: every other cell, the markers included, keeps its input color.

## Parameters
- `marker_color`: 2
- `line_paint`: 0 → 2, 1 → 3
    - the color a segment cell takes, keyed by its input color

## Scene parameters
- `field_colors`: 0, 1
