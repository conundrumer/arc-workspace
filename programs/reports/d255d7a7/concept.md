# d255d7a7

## Concept
- Each cup sits at one edge of the grid on a long handle, and it slides along its handle to the other end, carrying what is inside it; the handle is gone.

## Scene
- `background`: the grid is `background` everywhere outside the shapes and the marks.
- `cup`: each cup is a `frame` bracket of `cup-width` × `cup-width` cells that is open on one side, and its open side lies on a grid edge.
- `handle`: a straight `frame` line runs from the middle of each cup's closed side, away from its opening, to the opposite grid edge.
- `same-facing`: all cups of an input open toward the same edge.
- `cup-contents`: the cells inside a cup's bracket are `background` or `mark`.
- `loose-marks`: some `mark` cells lie outside every cup and handle.

## Rules
- `slide-to-handle-end`: each cup, with the cells inside its bracket, moves along its handle until its closed side lies on the grid edge where the handle ends.
- `clear-vacated`: the handle and the cup's old cells become `background`.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: 7
- `frame`: 0
    - the color of the cups and the handles

## Scene parameters
- `mark`: 9
- `cup-width`: 3
