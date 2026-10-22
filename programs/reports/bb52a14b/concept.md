# bb52a14b

## Concept
- One small patch is a key with some of its cells marked in `fill_color`; wherever the key's other cells occur again, with `background` where the key has its marks, the marks are filled in there too.

## Scene
- `scattered-cells`: on a field of `background`, cells of the `scatter_colors` lie scattered over the grid, singly and in small clumps.
- `one-key`: the cells of `fill_color` all lie in one box of `key_size`, the key, and the other cells of that box are of the `scatter_colors`.
- `bare-copies`: the key's non-`fill_color` cells occur again, at the same offsets from one another, at one or more places, each with `background` at the offsets of the key's marks.

## Rules
- `copy-input`: each cell of the output is the input's cell, except as the next rule says.
- `fill-copies`: the key is the bounding box of the `fill_color` cells; at each other place where a box of the key's extent has the key's cells at every offset other than the marks, and the cells at the offsets of its marks are `background`, those cells take `fill_color`.

## Parameters
- `fill_color`: 4
    - the color of the key's marks, and of the cells the output fills
- `background`: 0

## Scene parameters
- `scatter_colors`: 1, 8
- `key_size`: 3×3
