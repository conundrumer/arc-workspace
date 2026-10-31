# caa06a1f

## Concept
- A repeating pattern fills a block in one corner of the grid, and a band of one other color fills the rest; the output continues the pattern over the whole grid, moved one cell toward the block's corner.

## Scene
- `periodic-block`: a rectangular block at the `block_corner` corner of the grid holds a pattern of two or more colors that repeats along each axis, with at least two full periods along each axis.
- `background-band`: every cell outside the block holds one color that the pattern does not use, so the band lies along the two edges away from `block_corner`.

## Rules
- `extend-pattern`: the output has the input's size, and each output cell takes the color that the block's pattern, continued without end, has at that cell after the shift.
- `shift-one`: the continued pattern moves `shift_step` cells toward the block's corner on the axis `shift_axis` gives: for the top-left corner, on the horizontal axis output cell (r, c) takes the pattern's color at (r, c + 1), and on the vertical axis, at (r + 1, c).

## Parameters
- `shift_axis`: horizontal, vertical
    - the axis on which the pattern moves toward the block's corner; the train pairs have period 2 on both axes and do not separate the axes, and the test pair accepts each
- `shift_step`: 1
    - the number of cells the pattern moves
- `block_corner`: top-left
    - the corner the block sits at; the background color is the color at the opposite corner

## Scene parameters
- none
