# e48d4e1a

## Concept
- A cross of two full lines moves one step diagonally, toward the bottom-left, for each gray mark in the corner, and the marks are erased.

## Scene
- `full-cross`: one row and one column of one color, each running edge to edge, cross on a `bg` field.
- `mark-stack`: cells of `mark_color` stand in a run down the `mark_edge` edge from its `mark_corner` corner, and no other cell has that color.

## Rules
- `count-marks`: the shift is the number of `mark_color` cells.
- `shift-cross`: the cross's row moves `shift` cells toward one edge of `shift_dir`, and its column moves `shift` cells toward the other edge, and each line still runs edge to edge.
- `erase-marks`: every cell off the moved lines is `bg`.

## Parameters
- `shift_dir`: bottom-left
    - the corner that the crossing point moves toward
- `bg`: `0`
- `mark_color`: `5`

## Scene parameters
- `mark_corner`: top-right
- `mark_edge`: right
