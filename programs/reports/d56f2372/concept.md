# d56f2372

## Concept
- Several shapes lie on the background, and the output is the one shape that is mirror-symmetric about its own vertical axis, cut out by its bounding box.

## Scene
- `shapes-on-background`: every input holds several shapes on a field of `background`, each shape one color, and no two shapes share a color.
- `one-symmetric-shape`: exactly one shape is unchanged under the `symmetry` reflection of its bounding box, and every other shape is changed by it.

## Rules
- `crop-symmetric-shape`: the output is the bounding box of the shape that `symmetry` keeps, with the shape's cells in its color and every other cell `background`.

## Parameters
- `background`: `0`
- `symmetry`: `SYM_LR`
    - the reflection that keeps the chosen shape: the mirror about the vertical axis of the shape's bounding box

## Scene parameters
- none
