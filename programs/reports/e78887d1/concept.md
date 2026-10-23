# e78887d1

## Concept
- Each row of shapes is the row above it with the shapes moved one place to the left, the first shape wrapping to the end, and each shape takes the color of the place it lands in; the output is the next row in that sequence.

## Scene
- `glyph-tiling`: the input is cut into cells of `glyph-size` × `glyph-size`, with blank lines `gap` wide between cells on both axes; on the `band-axis`, a blank line `gap` wide also borders the first and the last band, and on the other axis no blank line borders the grid.
- `bands`: each line of cells along the `band-axis` is a band, and each cell of a band is a slot that holds one glyph: a pattern of one color on `background`.
- `slot-colors`: each slot position holds one color in every band, and different slot positions hold different colors.
- `band-shift`: each band after the first is the band before it with each glyph pattern moved `shift-step` slots toward `shift-dir`, a pattern that passes the slot nearest `shift-dir` wrapping round to the slot farthest from it, and each pattern drawn in the color of the slot it lands in.

## Rules
- `next-band`: the output is one band without its border lines: the last band with each glyph pattern moved `shift-step` slots toward `shift-dir`, a pattern that passes the slot nearest `shift-dir` wrapping round to the slot farthest from it, and each pattern drawn in the color of the slot it lands in.

## Parameters
- `shift-dir`: left
    - the direction along the band in which glyph patterns move from one band to the next
- `shift-step`: 1
    - the number of slots a glyph pattern moves from one band to the next
- `band-axis`: horizontal
    - the axis the bands run along: each band is a strip of rows
- `glyph-size`: 3
- `gap`: 1
- `background`: 0

## Scene parameters
none
