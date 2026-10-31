# f25fbde4

## Concept
- Cut out the drawing on the blank grid and blow it up to twice its size.

## Scene
- `blank-field`: the grid is filled with the background color `bg` apart from a drawing.
- `one-drawing`: the non-background cells form one small drawing of one color, `ink`, whose cells all join, at an edge or at a corner, set somewhere inside the grid.

## Rules
- `crop-to-drawing`: the output frame is the bounding box of the non-background cells.
- `scale-up`: each cell of the bounding box becomes a `factor` × `factor` block of the same color in the output.

## Parameters
- `bg`: 0
- `factor`: 2
    - the side of the block each cell of the cropped drawing becomes

## Scene parameters
- `ink`: 4
    - the color of the drawing
