# cdecee7f

## Concept
- Pick up the scattered colored dots from left to right and lay them into a small square in a snake order: the first row left to right, the next row right to left, and so on; the squares left over stay empty.

## Scene
- `scattered-dots`: on an `in-size` field of `bg`, a set of single colored cells, no two touching, even at a corner, no two in the same line across `scan-dir`, and no more of them than the cells of an `out-size` grid.

## Rules
- `scan-order`: the dots are ranked by their distance from the `scan-dir` edge of the input.
- `snake-fill`: the output is an `out-size` grid whose cells, in a snake path, take the dots' colors in rank order: the path starts at the `fill-corner` corner, runs along `fill-axis` to the far edge, steps one line across, and runs back, each line in the opposite direction from the one before.
- `empty-rest`: the output cells past the last dot on the path are `bg`.

## Parameters
- `bg`: `0`
- `scan-dir`: left
    - the edge from which the dots are ranked
- `out-size`: 3×3
- `fill-corner`: top-left
    - the corner of the output where the snake path starts
- `fill-axis`: horizontal
    - the axis of the path's lines

## Scene parameters
- `in-size`: 10×10
