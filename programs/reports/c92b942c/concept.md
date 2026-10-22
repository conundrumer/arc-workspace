# c92b942c

## Concept
- Tile the input 3 by 3, then through each mark draw a line of color 1 along its row, and put a color 3 cell at the two corners of the mark on one diagonal: up-left and down-right.

## Scene
- `marks-on-background`: the input is a field of `background` with one or more marks, all of one color other than 1 and 3, and the marks are fewer than the `background` cells.

## Rules
- `tile`: the output frame is the input repeated `tile-count` times on each axis.
- `row-line`: in the tiled grid, each `background` cell on a line along `line-axis` that holds a mark takes `line-color`.
- `diag-corners`: in the tiled grid, each `background` cell one diagonal step from a mark toward a corner in `diag-dirs` takes `diag-color`, over the line; a step that leaves the tiled grid paints nothing.
- `marks-kept`: each mark keeps its color, and every other cell keeps `background`.

## Parameters
- `tile-count`: 3
    - the number of copies of the input on each axis
- `background`: 0
- `line-axis`: H
- `line-color`: 1
- `diag-dirs`: TL, BR
- `diag-color`: 3

## Scene parameters
- none
