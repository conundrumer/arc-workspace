# e8686506

## Concept
- A frame with gaps sits among loose pieces; slide each piece, unturned, into the gap of its shape, and the filled frame is the output.

## Scene
- `background`: the commonest color fills the grid around everything else.
- `frame`: the frame is all cells of one or two frame colors, and no piece holds a frame color.
- `pieces`: every other non-background cell belongs to a piece, a 4-connected one-color part that touches no other non-background cell, even at a corner.
- `exact-fit`: the pieces, each translated, cover the background cells of the frame's bounding box exactly once, and no other cell.

## Rules
- `find-frame`: the frame colors are the set of colors at which `exact-fit` holds.
- `crop`: the output is the frame's bounding box, with the frame cells kept.
- `fill`: each background cell of that box takes the color of the piece that covers it in the exact cover.

## Parameters
- none

## Scene parameters
- none
