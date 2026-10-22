# ad38a9d0

## Concept
- Each small shape is painted in the color that its shape stands for: a plus, a line, a domino, an L, a Z, a block — each kind has its own color.

## Scene
- `field`: a field of `bg` holds separate pieces of `fg`, each a 4-connected component of `fg`.
- `known-shapes`: each piece's shape, read up to translation and an element of `shape_sym`, is a key of `shape_color`.

## Rules
- `recolor-by-shape`: each `fg` cell takes the color `shape_color` gives the key its piece's shape matches under `shape_sym`; every other cell keeps its color.

## Parameters
- `fg`: `6`
    - the color of the pieces
- `shape_color`: each shape, as its cells relative to the top-left of its bounding box, to its color
    - plus `(0,1), (1,0), (1,1), (1,2), (2,1)` → `3`
    - vertical line of 3 `(0,0), (1,0), (2,0)` → `2`
    - vertical domino `(0,0), (1,0)` → `9`
    - L `(0,0), (0,1), (1,1)` → `4`
    - Z `(0,0), (0,1), (1,1), (1,2)` → `8`
    - 2×3 block `(0,0)…(1,2)` → `5`
- `shape_sym`: `SYM_1`, `SYM_C4`, `SYM_D4`
    - the subgroup of D4 under which a piece's shape matches a key

## Scene parameters
- `bg`: `7`
