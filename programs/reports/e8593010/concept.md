# e8593010

## Concept
- Small holes in a solid field are recolored by their size: each single cell, each domino and each three-cell piece gets its own color.

## Scene
- `field-and-holes`: every input is a field of `field_color` with cells of `hole_color` scattered on it.
- `small-pieces`: each 4-connected piece of `hole_color` cells has a size that is a key of `size_color`.

## Rules
- `keep-field`: each `field_color` cell keeps its color.
- `color-by-size`: each cell of a 4-connected piece of `hole_color` takes the color that `size_color` gives for the piece's cell count.

## Parameters
- `hole_color`: `0`
- `size_color`: 1 → `3`, 2 → `2`, 3 → `1`
    - the color each piece size maps to

## Scene parameters
- `field_color`: `5`
