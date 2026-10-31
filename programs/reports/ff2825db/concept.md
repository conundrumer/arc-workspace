# ff2825db

## Concept
- A framed box holds scattered cells of two colors; the more numerous color wins: the box is cleared, the winner's cells are replaced by the outline of the rectangle that bounds them, drawn in the winner's color, and the frame is recolored to the winner too, while the palette strip above stays as it is.

## Scene
- `palette-strip`: the line of the grid at `strip_side` is the strip `strip_colors`, identical in every input.
- `frame`: below the strip, a 1-wide frame of one color runs around the rest of the grid, and encloses the box.
- `scattered-cells`: inside the frame the box is `background`, with scattered cells of exactly `scatter_color_count` other colors, neither of them the frame's color.
- `distinct-counts`: the two scattered colors have different cell counts.

## Rules
- `winner`: the winner is the scattered color with the most cells in the box.
- `keep-strip`: the palette strip is copied unchanged.
- `recolor-frame`: every frame cell takes the winner's color.
- `bbox-outline`: the cells on the edge of the bounding box of the winner's cells take the winner's color.
- `clear-rest`: every other cell inside the frame is `background`.

## Parameters
- `background`: 0
- `strip_side`: top
    - the side of the grid the palette strip lies on; the frame runs around the rest

## Scene parameters
- `strip_colors`: `1 1 2 2 3 3 4 4 5 5`
- `scatter_color_count`: 2
- `grid_size`: 10×10
