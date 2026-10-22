# 4c7dc4dd

## Concept
- Two framed panels each hold a pair of boxes. In one panel, the second box shows what a transformation makes of the first box's picture. In the other panel, one box holds a picture and the other is empty. The output is the empty box's interior, filled with what the same transformation makes of its partner's picture.

## Scene
- `clutter`: the field outside the panels is a repeating diagonal stripe of several colors, with scattered breaks.
- `panels`: two rectangular frames, each drawn in its own color, stand on the field.
- `boxes`: each panel holds two square boxes outlined in one color. Every box in the input has the same interior size, and a box's empty cells are `box_background`.
- `demo-query`: in one panel, the demo, both boxes hold a picture. In the other, the query, one box holds a picture and the other is all `box_background`.
- `repertoire`: the demo's two pictures are related by one transformation from a fixed repertoire, and the direction in which it holds is the one in which it maps one picture onto the other.
    - `connect`: two marks on one row or column are joined by a line of the non-`anchor` mark color through the cells between them.
    - `invert`: the marked cells become empty and the empty cells become marked. A cell takes the color its parity (row + column, even or odd) carries among the source's marks.
    - `mirror-fill`: the picture in one quarter is mirrored into the other three quarters, and the source's cells of the box outline color flood that color over the `box_background` cells they reach without crossing another mark.

## Rules
- `pick`: the transformation is the repertoire member that maps one demo picture onto the other.
- `apply`: the output is the query's empty box interior, with that transformation applied to the query's picture in the query's own colors.
- `size`: the output has the size of a box interior.

## Parameters
- `box_background`: 0
- `anchor`: 6
    - the mark color that a `connect` line never takes

## Scene parameters
- none
