# b20f7c8b

## Concept
- A legend strip at one side pairs each color with a small glyph. Each box on the board swaps between its two forms: a box that draws a glyph becomes a solid box of the color whose legend glyph it is, turned or flipped, and a solid box of a color becomes a box that draws that color's glyph as the legend shows it.

## Scene
- `legend-strip`: a strip of `panel_color`, `panel_width` cells wide, runs the full length of one side edge of the grid, and the rest of the grid is the board, of `board_color`.
- `legend-glyphs`: the strip holds glyphs, each the cells of one color that fill a `glyph_size` × `glyph_size` box, with each glyph its own color, none of them `panel_color`, and no two glyphs the same under `match_group`.
- `board-boxes`: the board holds `box_size` × `box_size` boxes, apart from one another on `board_color`, one box for each glyph of the legend.
- `box-forms`: each box is either a glyph box, a 1-wide frame of `frame_color` whose interior is `frame_color` with `ink_color` cells that fill the interior and equal one legend glyph under `match_group`, or a solid box of one legend glyph's color, and no two boxes stand for the same glyph.

## Rules
- `glyph-to-solid`: a glyph box becomes a solid box, all of the color of the legend glyph that its `ink_color` cells equal under `match_group`.
- `solid-to-glyph`: a solid box of a color becomes a glyph box: its 1-wide frame and interior take `frame_color`, and the interior takes `ink_color` at the cells of that color's legend glyph, untransformed.
- `rest-unchanged`: every cell outside the boxes keeps its color.

## Parameters
- `panel_color`: 8
- `board_color`: 0
- `frame_color`: 2
- `ink_color`: 1
- `match_group`: `SYM_D4`
    - the symmetries under which a glyph box's ink matches a legend glyph

## Scene parameters
- `panel_width`: 6
- `glyph_size`: 3
- `box_size`: 5
