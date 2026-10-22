# c62e2108

## Concept
- Each square that a marker at the grid edge lines up with repeats itself, copy against copy, in a line toward that marker until the grid edge cuts it off.

## Scene
- `background`: the field is color `background`.
- `squares`: one or more copies of one shape, a square outline of side `side` with a hollow middle, all in one color other than `background` and `marker`.
- `edge-markers`: one or more straight segments of color `marker`, each lying along a grid edge, as long as a square's side, and covering the same rows (on a left or right edge) or the same columns (on a top or bottom edge) as exactly one square.
- `clear-strip`: the strip between a square and each marker lined up with it holds only `background` and that marker.

## Rules
- `repeat-toward-marker`: each square repeats toward each marker lined up with it, each copy placed `gap` cells past the one before, so the copies tile the strip from the square to the grid edge, and the last copy is cut off at the grid edge.
- `copies-overwrite`: a copy writes every cell of its box, its hollow cells as `background`, so the marker cells take the copy's cells.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `marker`: 1
- `gap`: 0
    - the count of cells between one copy and the next

## Scene parameters
- `side`: 4
