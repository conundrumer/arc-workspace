# e9bb6954

## Concept
- Each solid square block shoots a full-length line of its own color through its center row and its center column, across the whole grid and over everything in the way; where the lines of two different blocks cross, the cell is cleared to background.

## Scene
- `background-field`: the field is `background`.
- `square-blocks`: one or more solid squares of side `block-size`, each a single color, each a whole 4-connected component of that color.
- `distinct-block-colors`: no two blocks share a color.
- `scattered-noise`: every other non-background cell is noise, in single cells or short runs, and no noise forms a solid square of side `block-size`.
- `separate-lines`: no two blocks share a row or a column, so no block's center row or center column is another block's.
- `lines-miss-blocks`: no block's center row or center column passes through another block.

## Rules
- `center-cross`: each block paints its center row and its center column, end to end, in its color, over noise and background.
- `crossing-cleared`: a cell on lines of two different blocks becomes `background`, whatever the input holds there.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `block-size`: 3

## Scene parameters
none
