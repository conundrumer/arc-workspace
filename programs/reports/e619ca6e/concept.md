# e619ca6e

## Concept
- Each block repeats as a staircase of copies of itself, going down and out to both sides, each copy touching the one before it at a corner, until the copies leave the grid.

## Scene
- `solid-blocks`: the input holds one or more solid rectangles of color `block_color` on a field of `background`, each its own component, apart from one another.

## Rules
- `diagonal-copies`: from each block, for each direction in `cast_dirs`, the output adds copies of that block, the k-th copy moved k times the block's height along the vertical part of the direction and k times its width along the horizontal part, for k = 1, 2, … while any of the copy is in the grid.
- `copy-keeps-block`: each copy has the shape and the color of its block, and the part of a copy that falls past the frame edge is dropped.
- `union`: the output is the input with every copy painted over it, and copies that overlap one another or a block leave the cell in the block color.

## Parameters
- `background`: `0`
- `cast_dirs`: {bottom-left, bottom-right}
    - the diagonal directions along which each block's copies go

## Scene parameters
- `block_color`: `3`
