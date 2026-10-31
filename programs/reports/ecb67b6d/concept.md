# ecb67b6d

## Concept
- Among the clumps of grey cells, the ones that hold a straight diagonal line at least three cells long are recolored; every other clump stays as it is.

## Scene
- `marks-on-field`: every input is a field of `background` with cells of `mark_color` scattered over it, and holds no other color.
- `clumps`: the `mark_color` cells group into clumps, each a set of cells joined through side and corner contact (8-adjacency).

## Rules
- `diagonal-run`: a clump holds a diagonal run when `min_run` of its cells lie one after another along a diagonal line of either diagonal axis, each next to the one before it at a corner.
- `recolor-clump`: every cell of a clump that holds a diagonal run takes `fill_color`.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `mark_color`: 5
- `fill_color`: 8
- `min_run`: 3
    - the fewest cells of a straight diagonal run that makes a clump recolor

## Scene parameters
- `background`: 7
