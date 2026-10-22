# da6e95e5

## Concept
- Several shapes each sit inside a frame of four corner brackets; output the one shape drawn in the same color as its own frame.

## Scene
- `background`: one color fills every cell that no frame or shape covers.
- `bracket-frames`: each frame is four L-shaped corner brackets of one color, the corners of a rectangle, with gaps between them along each side.
- `framed-shape`: inside each frame's rectangle, clear of the brackets, sits one shape of one color, connected under 8-adjacency.
- `one-match`: exactly one frame has a shape of the frame's own color.

## Rules
- `crop-matching-shape`: the output is the bounding box of the shape whose color equals its frame's color, with that shape's cells in its color and every other cell in the background color.

## Parameters
- none

## Scene parameters
- none
