# e40b9e2f

## Concept
- A figure is drawn only in part of a pattern with four-fold rotational symmetry: complete it by adding the quarter-turn images of its cells about the center of its square core.

## Scene
- `one-figure`: the grid holds one figure of non-`bg` cells on a field of `bg`, which may be disconnected at corners.
- `square-core`: the figure holds one largest solid square block that each element of `group` about its own center maps onto itself, colors included; this is the core.
- `consistent-images`: the quarter-turn images of the figure about the core center fall inside the grid, and no two of them give one cell two different colors.

## Rules
- `quarter-turn-completion`: each figure cell, under each element of `group` about the core center (a quarter, a half and three quarters turn), paints its color at its image cell.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `bg`: 0
    - the field color
- `group`: `SYM_C4`
    - the symmetry group whose images the figure gains

## Scene parameters
- none
