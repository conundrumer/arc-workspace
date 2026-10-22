# bd14c3bf

## Concept
- A red reference shape sits in a corner, and each blue shape that is the reference shape stretched, turned or mirrored turns red.

## Scene
- `reference-shape`: one 4-connected shape of `ref_color` touches the `ref_corner` corner of the grid, and no other cell has that color.
- `mark-shapes`: the other non-background cells are `mark_color`, in 4-connected shapes that do not touch one another, even at a corner.

## Rules
- `stretch-match`: a mark shape matches the reference shape when each shape, cut down to its bounding box and with each run of identical adjacent rows and each run of identical adjacent columns cut to one line, gives the same grid up to a transform of `match_group`.
- `recolor-match`: each mark shape that matches turns `ref_color`.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- `ref_color`: 2
- `mark_color`: 1
- `match_group`: `SYM_C4`, `SYM_D4`
    - the transforms under which two reduced shapes count as the same

## Scene parameters
- `ref_corner`: `DIAG_TL`
- `background`: 0
