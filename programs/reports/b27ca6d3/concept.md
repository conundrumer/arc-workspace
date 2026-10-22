# b27ca6d3

## Concept
- Red marks lie scattered on a black field, some alone and some in side-by-side pairs; draw a green frame around each pair.

## Scene
- `field`: every cell that is not a mark has the `background` color.
- `marks`: the marks are cells of the `mark` color, and each group of marks joined by shared sides is one cell or has `pair_size` cells.

## Rules
- `pick-pairs`: a group of marks joined by shared sides that has `pair_size` cells is a pair; a mark that touches others only at a corner does not join them.
- `frame`: each background cell that touches a cell of a pair at a side or a corner takes the `frame` color.
- `keep`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `mark`: 2
- `frame`: 3
- `pair_size`: 2
    - the number of cells a group of marks has when it gets a frame

## Scene parameters
none
