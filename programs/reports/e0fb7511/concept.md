# e0fb7511

## Concept
- On a field of `1`, scattered `0` cells form groups by 4-adjacency; every group of two or more cells is recolored to `8`, and each lone `0` cell stays.

## Scene
- `field-with-marks`: the grid is a field of `background` with scattered cells of `mark`, and holds no other color.

## Rules
- `recolor-groups`: each 4-connected component of `mark` cells with at least `min_size` cells takes `fill` in every cell.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `mark`: 0
    - the color whose components the rule measures
- `fill`: 8
    - the color a recolored component takes
- `min_size`: 2
    - the least component size that is recolored

## Scene parameters
- `background`: 1
