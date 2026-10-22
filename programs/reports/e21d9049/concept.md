# e21d9049

## Concept
- A short horizontal strip and a short vertical strip of colors cross; each strip repeats its color sequence along its whole row or column, out to both grid edges.

## Scene
- `crossing-strips`: on a field of `background`, the non-background cells form one horizontal strip and one vertical strip, each one cell wide, that share exactly one cell, where they cross.
- `distinct-colors-per-strip`: no color occurs twice in one strip.
- `equal-length`: the two strips have the same length.

## Rules
- `repeat-along-line`: each cell of a strip's row (for the horizontal strip) or column (for the vertical strip) takes the color of the strip cell whose distance from it along the line is a multiple of the strip's length, so the strip's color sequence repeats with a period of its length and the strip's own cells keep their colors.
- `rest-unchanged`: every cell on neither line keeps its input color.

## Parameters
- `background`: 0

## Scene parameters
none
