# d90796e8

## Concept
- Wherever a green cell touches a red cell side by side, the two merge into one cell: the green cell turns purple and the red cell is erased.

## Scene
- `scattered-single-cells`: on a `background` field, the input holds single cells of `merge-color`, `absorbed-color` and other colors, with no two cells of one color side by side.
- `pairs-disjoint`: each `merge-color` cell touches at most one `absorbed-color` cell side by side, and each `absorbed-color` cell touches at most one `merge-color` cell side by side.

## Rules
- `merge-pair`: a `merge-color` cell that has an `absorbed-color` cell as a 4-neighbor takes `result-color`, and that `absorbed-color` cell takes `background`.
- `keep-rest`: every other cell keeps its input color, a lone `merge-color` or `absorbed-color` cell included.

## Parameters
- `merge-color`: 3
    - the color of the cell of a pair that stays and takes `result-color`
- `absorbed-color`: 2
    - the color of the cell of a pair that is erased
- `result-color`: 8
- `background`: 0

## Scene parameters
- none
