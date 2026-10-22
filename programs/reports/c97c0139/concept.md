# c97c0139

## Concept
- Each straight line is the diagonal of a diamond (a square turned 45°), and the diamond around it is filled in.

## Scene
- `segments`: every input holds, on a `background` field, one or more straight segments of `line_color`, each one cell wide, horizontal or vertical, and at least two cells long.
- `apart`: the diamond of each segment lies inside the grid, and it meets no cell of another segment or of another segment's diamond.

## Rules
- `diamond-fill`: a `background` cell at distance d from a segment's line, measured across the line, takes `fill_color` when both cells d steps along the line from the cell's foot on the line are cells of that segment.
    - The foot is the cell of the line nearest the cell, and d is at least 1.
- `keep`: every other cell keeps its input color, so each segment stays.

## Parameters
- `background`: 0
- `fill_color`: 8

## Scene parameters
- `line_color`: 2
