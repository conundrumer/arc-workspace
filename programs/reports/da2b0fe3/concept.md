# da2b0fe3

## Concept
- A figure is cut into two parts by one empty line; draw that line in green from edge to edge of the grid.

## Scene
- `one-figure`: every non-`background` cell has one color, and those cells form one figure on a field of `background`.
- `one-gap-line`: exactly one row or column that crosses the figure's bounding box holds no figure cell, and it splits the figure into a part on each side.

## Rules
- `gap-lines`: the lines drawn are the rows and columns that cross the figure's bounding box and hold no figure cell.
- `full-span`: each drawn line runs across the whole grid, and every cell on it is set to `line_color`; every other cell keeps its input color.

## Parameters
- `line_color`: 3

## Scene parameters
- `background`: 0
