# d753a70b

## Concept
- Each shape is a diamond outline around a center cell. A diamond of the shrink color gets one step smaller, a diamond of the grow color gets one step bigger, and a diamond of any other color stays as it is. The frame clips a diamond that reaches past it.

## Scene
- `background`: every cell that is not part of a shape has the color `background`.
- `diamond-outlines`: each shape is one color, and its cells are the cells inside the frame at one taxicab distance r ≥ 0 from a center cell inside the frame. A diamond of radius 0 is a single cell.
- `diamonds-apart`: two diamonds of one color share no cell and do not touch, also at a corner.

## Rules
- `shrink`: a diamond of color `shrink_color` becomes the diamond of radius r − 1 around the same center, clipped by the frame.
- `grow`: a diamond of color `grow_color` becomes the diamond of radius r + 1 around the same center, clipped by the frame.
- `keep`: a diamond of any other color stays unchanged.
- `size`: the output has the input's size, and every cell that no output diamond takes has the color `background`.

## Parameters
- `background`: 7
- `shrink_color`: 2
- `grow_color`: 5

## Scene parameters
- none
