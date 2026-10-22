# e048c9ed

## Concept
- Each bar gets a mark in the marker's column on its own row, and the mark's color says the bar's length: 2 is blue, 3 is yellow, 4 is maroon, 5 is magenta.

## Scene
- `background`: a field of `background`.
- `one-marker`: exactly one object is a single cell; it sits on the `marker_edge` row, in color `marker_color`.
- `bars`: every other object is a straight one-color bar along `bar_axis`, of length 2 or more, each on its own line, with lines of background between bars.
- `bars-short-of-marker`: every bar lies wholly on the `bar_side` side of the marker's line across `bar_axis`, so no bar meets that line.
- `bar-lengths-known`: each bar's length is a key of `length_color`.

## Rules
- `mark-per-bar`: for each bar, the cell where the bar's line meets the marker's line across `bar_axis` takes the color `length_color` gives the bar's length; the bar's own color does not count.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `bar_axis`: H
    - the axis the bars run along
- `length_color`: 2 → 1, 3 → 4, 4 → 9, 5 → 6
    - a lookup table from a bar's cell count to the mark's color

## Scene parameters
- `marker_color`: 5
- `marker_edge`: T
- `bar_side`: L
    - the side of the marker's column that the bars lie on
