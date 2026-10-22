# c663677b

## Concept
- The grid is a wallpaper: one tile repeats across it on both axes. Some patches of it are blanked out with `hole_color`, and the output fills each blanked cell back in from the repeat.

## Scene
- `periodic-pattern`: apart from the blanked cells, the grid is periodic on each axis: each cell has the color of every cell that lies a whole number of periods away from it on the row axis and on the column axis. The period on an axis is shorter than the grid on that axis.
- `blanked-patches`: some cells are blanked, each with `hole_color`. The blanked cells form one or more patches. `hole_color` occurs nowhere in the pattern.
- `each-class-seen`: for each blanked cell, some cell a whole number of periods away from it on each axis is not blanked.

## Rules
- `restore-pattern`: the output is the input with each blanked cell given the color that the unblanked cells of its class under the periods hold.

## Parameters
- `hole_color`: 0
    - the color that marks a blanked cell

## Scene parameters
- none
