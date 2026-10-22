# e45ef808

## Concept
- A mountain range stands under a sky. A line of one color drops from the top of the sky onto the highest peak, and a line of another color drops into the deepest valley.

## Scene
- `border-row`: the line at the edge opposite `ground_side` is all `border_color`.
- `sky-and-ground`: every other cell is `sky_color` or `ground_color`.
- `solid-ground`: in each column, the `ground_color` cells are one run that starts at the `ground_side` edge, so each column has a ground height.
- `sky-in-every-column`: each column has at least one `sky_color` cell, and at least one `ground_color` cell.
- `one-deepest-valley`: exactly one column has the least ground height.

## Rules
- `peak-line`: the column with the greatest ground height takes `peak_color` in each of its `sky_color` cells. Where columns tie for the greatest height, the one nearest the `tie_side` edge takes it.
- `valley-line`: the column with the least ground height takes `valley_color` in each of its `sky_color` cells.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `sky_color`: 1
- `ground_color`: 6
- `peak_color`: 4
- `valley_color`: 9
- `ground_side`: B
    - the edge that the ground rises from
- `tie_side`: R
    - the edge whose nearest column wins a tie for the highest peak

## Scene parameters
- `border_color`: 0
