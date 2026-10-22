# d37a1ef5

## Concept
- A rectangular frame holds a few scattered marks; the frame thickens inward until it reaches the bounding box of the marks, so only that box stays open.

## Scene
- `background`: the grid is `background` outside the frame and in the frame's empty interior cells.
- `one-frame`: every input holds one 1-wide rectangle outline in `frame_color`, with an interior at least one cell wide on each axis.
- `marks-inside`: every input holds one or more `mark_color` cells, all inside the frame's interior, and no other cell of the interior is non-`background`.
- `gap-to-frame`: no mark touches the frame; at least one interior row or column lies between the marks' bounding box and each side of the frame.

## Rules
- `fill-outside-box`: each interior cell of the frame outside the bounding box of the marks becomes `frame_color`.
- `keep-box`: each cell inside the bounding box of the marks keeps its input color, marks and `background` cells alike.
- `keep-rest`: the frame and every cell outside it keep their input color.

## Parameters
- `background`: 0
- `frame_color`: 2
    - the color of the outline, which the fill takes

## Scene parameters
- `mark_color`: 5
