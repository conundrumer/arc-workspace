# ea959feb

## Concept
- A wallpaper pattern that repeats along both axes has solid patches of one color painted over it; take the patches off and show the pattern under them.

## Scene
- `periodic-pattern`: the grid is a pattern that repeats along each axis, with a period on each axis that is shorter than the grid, so each cell's row phase and column phase recur elsewhere in the grid.
- `mask-patches`: solid rectangles of `mask_color` cover parts of the pattern, and they cover fewer cells than the pattern shows elsewhere at each phase pair.
- `mask-color-in-pattern`: `mask_color` is also one of the pattern's own colors, so a cell of that color is a masked cell or a pattern cell.
- `phase-uncovered`: each pair of a row phase and a column phase has a cell outside every patch.

## Rules
- `restore-period`: each cell of the output takes the color the pattern has at its row phase and column phase, which the cells outside the patches show; a cell outside the patches keeps its color.

## Parameters
- `mask_color`: 1
    - the color of the patches

## Scene parameters
- none
