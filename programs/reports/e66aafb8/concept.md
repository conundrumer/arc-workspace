# e66aafb8

## Concept
- A symmetric pattern has a patch blacked out; give the patch's hidden contents, read off the patch's mirror image.

## Scene
- `symmetric-pattern`: the input is a square pattern that every symmetry in `symmetry` maps onto itself, apart from the masked cells.
- `one-mask`: one solid rectangle of color `mask_color` covers part of the pattern, and no other cell has that color.
- `mask-image-visible`: some symmetry in `symmetry` maps the masked rectangle onto cells that the mask does not cover.

## Rules
- `restore-by-symmetry`: each masked cell takes the color that its unmasked images under the symmetries in `symmetry` share.
- `crop-to-mask`: the output is the masked rectangle, cropped from the restored pattern.

## Parameters
- `mask_color`: 0
- `symmetry`: SYM_D4
    - the subgroup of D4, about the grid's center, that every input keeps off the mask

## Scene parameters
- none
