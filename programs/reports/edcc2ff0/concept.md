# edcc2ff0

## Concept
- A legend lists colors; in the field below, objects of unlisted colors are wiped, and each legend marker grows into a bar as long as the number of field objects of its color, vanishing when there are none.

## Scene
- `legend-panel`: a full-width panel of `panel_color` sits on the `panel_side` of the grid, `panel_rows` rows deep, and holds one single-cell marker per listed color at the `bar_dir`-opposite edge, on rows `marker_rows`, each marker a distinct color.
- `field`: the rest of the grid is a field of one background color, which varies by input and is neither `panel_color` nor a listed color; the field holds no `panel_color` cell.
- `field-objects`: the field holds separate solid objects (bars, squares, an L), each of one color, no two of a color touching; some are of listed colors and some of unlisted ones.

## Rules
- `drop-unlisted`: every field object whose color no legend marker has becomes field background; objects of listed colors stay as they are.
- `tally-bars`: each legend marker becomes a bar on its row, starting at the marker's cell and running toward `bar_dir`, whose length is the number of field objects of the marker's color; a count of zero erases the marker to `panel_color`.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `panel_color`: 0
    - the panel's background, which tells panel cells from field cells and markers from panel
- `bar_dir`: DIR_R
    - the direction a bar runs from its marker

## Scene parameters
- `panel_side`: DIR_T
- `panel_rows`: 7
- `marker_rows`: 1, 3, 5
- `grid_size`: 20×10
