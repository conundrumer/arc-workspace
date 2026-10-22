# cfb2ce5a

## Concept
- A two-color tile fills one corner quadrant of a square. Mirror the tile into the other three quadrants, and recolor each copy by the marker cells in its quadrant: a marker shows what the tile color under it becomes there, and a tile color with no marker in that quadrant becomes background.

## Scene
- `source-tile`: the `source_corner` quadrant of a square holds a full tile of side `tile_size` in `tile_colors` colors, none of them `background`.
- `diagonal-symmetric-tile`: the tile is symmetric across its diagonal through `source_corner`.
- `square-in-border`: the square is the grid inset by `border` on every side, has side 2 × `tile_size`, and the border is `background`.
- `sparse-markers`: each other quadrant holds a few non-`background` marker cells and is `background` elsewhere.
- `consistent-markers`: in one quadrant, the markers over cells that mirror one tile color share one color.

## Rules
- `mirror-into-quadrants`: each other quadrant takes the tile reflected across the line or lines that part it from the source quadrant: across the vertical midline for the quadrant beside it, across the horizontal midline for the quadrant below or above it, and across both for the diagonal quadrant.
- `recolor-by-marker`: in a quadrant, each cell of a tile color takes the color of the markers that sit over that tile color in that quadrant.
- `unmarked-to-background`: in a quadrant, each cell of a tile color that no marker in that quadrant sits over is `background`.
- `rest-kept`: the source quadrant and the border are as in the input.

## Parameters
- `source_corner`: TL
    - the corner whose quadrant holds the full tile
- `background`: 0
- `border`: 1
    - the width of the border around the square

## Scene parameters
- `tile_size`: 4
- `tile_colors`: 2
