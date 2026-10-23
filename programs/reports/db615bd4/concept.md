# db615bd4

## Concept
- A dotted rectangle is a box, and the dotted pieces lying outside it are packed into it as solid blocks, in one line along the box's long side and in their order along that side, a `gap` apart.

## Scene
- `dot-class`: a background field with a dot of one dot color at each cell on the dot class, the cells whose row and column both have the `dot-parity`.
- `frame`: one color draws the outline of a rectangle on the dot class, a dot at each dot-class cell of that outline, in place of the dot color.
- `frame-interior`: inside the frame outline, the dot-class cells hold the dot color, and the other cells the background.
- `pieces`: two or more pieces, each in its own color, distinct from the background, the dot color and the frame color; each piece has a dot at each cell of a rectangle whose row and column both have the `piece-parity`, at a spacing of 2, and no other cell.
- `pieces-outside`: every piece lies outside the frame's bounding box.
- `pieces-apart`: along the frame's long axis, the spans of the pieces' bounding boxes are pairwise disjoint.
- `common-cross-extent`: across the frame's long axis, the pieces' bounding boxes have one extent.
- `exact-fit`: along the frame's long axis, the pieces' bounding-box extents with `gap` between consecutive ones add up to the interior extent less `margin` at each end.
- `cross-room`: across the long axis, the interior extent less the common block extent is even and at least 2 × `margin`.

## Rules
- `solid-outline`: every cell of the frame outline takes the frame color.
- `clear-interior`: every interior cell of the frame takes the background, before the blocks are drawn.
- `lift-pieces`: every piece cell takes the background.
- `stack-blocks`: each piece becomes a solid block of its color the size of its bounding box; the blocks line up in the frame interior along the frame's long axis, in the order of the pieces along that axis, `gap` cells between consecutive blocks, and the stack is centered in the interior on both axes.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `gap`: 1
    - the background cells between consecutive blocks along the stack

## Scene parameters
- `dot-parity`: odd row, odd column
- `piece-parity`: even row, even column
- `margin`: 1
    - the background cells between the end blocks of the stack and the frame outline
