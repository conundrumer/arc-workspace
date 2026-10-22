# cb227835

## Concept
- Two marker cells are the opposite corners of a slanted parallelogram: one pair of its sides runs diagonally and the other pair runs straight along a row or a column, and the outline is drawn between the markers in a line color.

## Scene
- `two-markers`: on a field of `background`, the input holds exactly two cells of `marker_color`, and no other cell.
- `markers-off-lines`: the two markers share no row, no column, and no diagonal, so the row offset and the column offset between them are both nonzero and differ in size.

## Rules
- `two-king-paths`: from each marker, the output draws the two shortest king-move paths to the other marker that are one straight run and one diagonal run: a straight run of |dr − dc| cells along the axis of the larger offset and a diagonal run of min(dr, dc) cells toward the other marker, in each of the two orders. The cells of those paths, the markers excluded, take `path_color`.
- `markers-kept`: the markers keep `marker_color`, and every other cell keeps its input color.

## Parameters
- `marker_color`: 8
- `path_color`: 3

## Scene parameters
- `background`: 0
