# d304284e

## Concept
- A shape repeats across the grid in a row of copies; every third copy is recolored, and each recolored copy repeats in its new color down to the bottom edge.

## Scene
- `one-shape`: every input holds one 8-connected shape of color `shape_color` on a field of `background`, and nothing else.
- `room-ahead`: the shape lies clear of the edges toward `march_dir` and `branch_dir`, with room for more than one copy toward `march_dir`.

## Rules
- `march`: copies of the shape repeat from it toward `march_dir`, each one `gap` cells past the one before, up to the grid edge; a copy the edge cuts is drawn in part.
- `mark-every-period`: numbering the run from the shape as copy 1, each copy whose number is a multiple of `period` is drawn in `mark_color`, and every other copy keeps the shape's colors.
- `branch`: from each marked copy, copies in `mark_color` repeat toward `branch_dir`, each one `gap` cells past the one before, up to the grid edge, drawn in part where the edge cuts them.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `march_dir`: right
    - the direction of the row of copies
- `branch_dir`: down
    - the direction the marked copies repeat in, on the other axis from `march_dir`
- `gap`: 1
    - the cells of background between two consecutive copies, on both axes
- `period`: 3
- `mark_color`: 6

## Scene parameters
- `shape_color`: 7
