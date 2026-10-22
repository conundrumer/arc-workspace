# c074846d

## Concept
- A stick hinged on a pivot cell swings a quarter turn around the pivot, and the place it left is marked in another color.

## Scene
- `pivot`: the input holds one cell of color `pivot_color`.
- `arm`: the input holds a straight run of `arm_color` cells, one cell wide, that starts at a neighbor of the pivot and goes away from it in one cardinal direction, of length one or more.
- `blank-field`: every other cell is `background`.
- `room-to-turn`: the grid holds the arm's full length past the pivot in the direction the turn takes it to.

## Rules
- `swing`: the output paints the arm at the pivot again, turned a quarter turn in sense `sense` around the pivot: each arm cell at distance k from the pivot in direction d goes to distance k in the direction `sense` turns d to, in `arm_color`.
- `trail`: each cell the arm held in the input takes `trail_color`.
- `keep`: every other cell, the pivot included, keeps its input color.

## Parameters
- `pivot_color`: 5
- `arm_color`: 2
- `trail_color`: 3
- `sense`: clockwise
    - the sense of the quarter turn

## Scene parameters
- `background`: 0
