# fbf15a0b

## Concept
- Two marker cells sit along one edge of the grid; cut the grid in half across the line the pair runs along, keep the half the markers are in, and erase the markers.

## Scene
- `background`: every cell not otherwise named holds the color `background`.
- `marker-pair`: exactly two cells hold `marker_color`; they lie on one edge line of the grid, on one row or one column, with `marker_gap` background cells between them, both in one half of the grid along that line.
- `even-extent`: the grid's extent along the line the pair runs along is a multiple of `part_count`.
- `pattern`: the remaining cells form a dot pattern in one other color, which nothing in the output reads apart from copying it.

## Rules
- `halve-along-pair`: the input is cut into `part_count` equal parts along the axis the pair runs along (rows when the pair shares a column, columns when it shares a row), each part with the full extent across.
- `keep-marker-half`: the output is the part holding the markers, copied cell for cell.
- `erase-markers`: each marker cell becomes `background` in the output.

## Parameters
- `marker_color`: 5
- `background`: 8
- `part_count`: 2
    - the number of equal parts the grid is cut into along the pair's axis

## Scene parameters
- `marker_gap`: 1
    - the number of background cells between the two markers along their line
