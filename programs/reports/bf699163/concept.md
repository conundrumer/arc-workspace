# bf699163

## Concept
- A dashed frame marks off one of several hollow squares, and the output is that square.

## Scene
- `background`: a field of `background`.
- `rings`: several hollow squares of side `ring_side`, each one color, no two of the same color, none of the frame color.
- `dashed-frame`: dashed straight lines of `frame_color` that are sides of one axis-aligned rectangle; the sides that the grid holds meet at the rectangle's corners, the other sides lie past the grid edge, and each line has gaps.
- `one-ring-inside`: exactly one ring lies inside that rectangle, clear of its sides, and every other ring lies outside it.

## Rules
- `crop-enclosed-ring`: the output is the bounding box of the ring inside the frame, copied from the input, its hole included.

## Parameters
- `frame_color`: 7
- `background`: 5

## Scene parameters
- `ring_side`: 3
