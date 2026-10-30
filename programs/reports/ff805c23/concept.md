# ff805c23

## Concept
- A mirror-symmetric pattern has a solid square painted over part of it; output what the square hides, restored from the pattern's symmetry.

## Scene
- `square-grid`: the input is a square grid of size `grid_size`.
- `symmetric-pattern`: the input, apart from the masked cells, is a pattern unchanged under each element of the group `symmetry` about the grid's center.
- `solid-mask`: one solid rectangle of color `mask_color`, of size `mask_size`, covers part of the pattern; `mask_color` occurs nowhere else.
- `mask-recoverable`: each masked cell has an image under `symmetry` that the mask does not cover.

## Rules
- `crop-mask`: the output is the mask's bounding box.
- `restore-by-symmetry`: each output cell takes the color of the images of its cell under `symmetry` that the mask does not cover.

## Parameters
- `mask_color`: 1
- `symmetry`: SYM_BOX, SYM_D4
    - the symmetry group about the grid's center that the restoration reads; every input holds under both, and the pairs do not separate them; the case runs every value and is undefined on an input where those values give different outputs

## Scene parameters
- `mask_size`: 5×5
- `grid_size`: 24×24
