# e509e548

## Concept
- Each green line drawing is recolored by its shape: an L becomes blue, a U becomes magenta, and any other shape becomes red.

## Scene
- `thin-drawings`: the input holds drawings of `shape_color` on a field of `bg`, each a connected set of 1-wide straight segments, and no two drawings touch, even at a corner.
- `three-kinds`: each drawing is an L (a path with one bend), a U (a path with two bends that turn the same way, so both ends point to the same side), or a branched drawing (a path with a side segment that leaves it at a T junction).

## Rules
- `recolor-by-kind`: the output is the input with each drawing's cells in the color `kind_color` gives the drawing's kind: L, U, or other.

## Parameters
- `bg`: 0
- `kind_color`: L → 1, U → 6, other → 2
    - the color of each drawing kind

## Scene parameters
- `shape_color`: 3
