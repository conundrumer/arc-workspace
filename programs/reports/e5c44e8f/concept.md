# e5c44e8f

## Concept
- A square spiral grows outward from a seed cell, with one empty line between its turns, and stops at the last cell before the first obstacle on its path.

## Scene
- `one-seed`: the input holds exactly one cell of `seed_color` on a field of `background`.
- `scattered-obstacles`: the other non-background cells are single cells of `obstacle_color`.
- `obstacle-before-edge`: the spiral path from the seed meets an obstacle cell before it leaves the grid.

## Rules
- `spiral-path`: the path starts at the seed and runs in arms along `first_dir`, then turns a quarter turn in `turn_sense` at the end of each arm; arms k = 0, 1, 2, ... have length (`gap` + 1) · (⌊k/2⌋ + 1), so arms 2, 2, 4, 4, 6, 6, ... at `gap` 1.
- `stop-at-obstacle`: the path ends at the last cell before its first cell that is an obstacle; the obstacle keeps its color.
- `paint-path`: each cell of the path takes `seed_color`, and every other cell keeps its input color.

## Parameters
- `first_dir`: up
    - the direction of the first arm
- `turn_sense`: clockwise
    - the sense of the quarter turn at the end of each arm
- `gap`: 1
    - the number of empty lines between two parallel arms of successive turns
- `obstacle_color`: 2
- `seed_color`: 3

## Scene parameters
- `background`: 0
