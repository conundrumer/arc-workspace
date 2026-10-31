# fafd9572

## Concept
- A small colored key is a map of the copies of one shape: each copy is recolored with the key cell that sits at the same place in the key as the copy sits in the arrangement of copies.

## Scene
- `key`: one small 8-connected patch of cells, none of `background` or `shape_color`, each in its own color slot; every row and every column of its bounding box holds a key cell.
- `copies`: identical copies of one shape in `shape_color`, laid on a lattice whose period on each axis is the shape's extent plus `copy_gap`, one copy per filled lattice slot.
- `layout-matches-key`: the filled lattice slots, read by row rank and column rank among the copies, are exactly the key's cells, read by their row and column within the key's bounding box.

## Rules
- `recolor-copy`: each copy takes the color of the key cell whose row and column within the key equal the copy's row rank and column rank among the copies.
- `keep-rest`: the key and the background are unchanged.

## Parameters
- `background`: 0
- `shape_color`: 1
    - the color of the uncolored copies, which marks them apart from the key

## Scene parameters
- `copy_gap`: 1
    - the background lines between two neighboring copies
