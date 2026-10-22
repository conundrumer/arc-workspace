# af726779

## Concept
- A line of marks grows a stack of levels toward one side: each single-cell gap between two marks gets a mark two lines further on, and the new marks do the same again, the levels taking turns between two colors, until a level has no such gap or the next level falls off the grid.

## Scene
- `background`: every cell off the base line is `background`.
- `base-line`: one full line across `growth-dir` holds marks of `mark-color` and cells of `background`, and no other color.
- `room-ahead`: the grid has lines past the base line on its `growth-dir` side.

## Rules
- `keep-input`: every input cell keeps its color.
- `gap-mark`: where a level has a mark on each of the two cells beside a cell along the level, and no mark on that cell, the cell `level-step` lines from it toward `growth-dir` becomes a mark of the next level.
- `levels`: the base line's marks are level 0, and the marks that `gap-mark` makes from level k are level k+1.
- `level-color`: a level's marks take the color `level-colors` gives for the parity of its index.
- `stop`: a level whose line is off the grid, or that has no mark, makes no further level.

## Parameters
- `growth-dir`: down
    - the side of the base line that the levels grow toward
- `level-step`: 2
    - the number of lines from one level to the next
- `level-colors`: 7 at even levels, 6 at odd levels
- `background`: 3

## Scene parameters
- `mark-color`: 7
    - the color of the base line's marks
