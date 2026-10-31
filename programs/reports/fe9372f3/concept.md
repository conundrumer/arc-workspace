# fe9372f3

## Concept
- A small plus shoots rays to the edges of the grid: plain diagonal rays from its center, and dashed rays out of its four arm tips that repeat two plain cells then one accent cell.

## Scene
- `one-plus`: one plus of `plus_color` on a field of `background`: a center cell and its four cardinal arms, each `arm_length` cells long, every other cell `background`.

## Rules
- `keep-input`: every input cell keeps its color unless a ray below paints it.
- `diagonal-rays`: from the center (the non-`background` cell whose four neighbors are non-`background`) toward each of the four diagonal directions, every cell from distance 1 to the grid edge takes `diag_color`.
- `dashed-cardinal-rays`: from each arm tip (the last non-`background` cell of the run out of the center) toward its own cardinal direction, the cell k steps past the tip, for k from 1 to the grid edge, takes `dash_pattern[(k - 1) mod |dash_pattern|]`.

## Parameters
- `background`: 0
- `diag_color`: 1
- `dash_pattern`: 8 8 4
    - the cyclic color sequence of a cardinal ray, from the cell next to the arm tip outward; its length 3 is the period.

## Scene parameters
- `plus_color`: 2
- `arm_length`: 1
