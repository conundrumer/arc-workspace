# d2abd087

## Concept
- Recolor each gray shape by its size: a shape of exactly six cells turns red, and every other shape turns blue.

## Scene
- `shapes-on-background`: a background of color `background` with several shapes of color `shape_color` on it; a shape is a 4-connected component of the `shape_color` cells.

## Rules
- `size-match-recolor`: each cell of a shape whose cell count equals `target_size` takes color `match_color`.
- `size-miss-recolor`: each cell of a shape whose cell count differs from `target_size` takes color `other_color`.
- `rest-kept`: every cell outside the shapes keeps its color.

## Parameters
- `shape_color`: 5
- `target_size`: 6
    - the cell count that selects a shape for `match_color`
- `match_color`: 2
- `other_color`: 1

## Scene parameters
- `background`: 0
