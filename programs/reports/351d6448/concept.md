# 351d6448

## Concept
- The panels are successive frames of a steady motion, and the output is the frame after the last one.

## Scene
- `panels`: full lines of `divider_color`, `divider_width` wide, cut the grid along `panel_axis` into `panel_count` panels of one size.
- `steady-step`: each panel is the one before it with one change applied, and that change is the change from the first panel to the second, moved a fixed count of cells along the other axis once per frame (train0: the object `2 2 3` moves one column right; train1: the run of `1` grows by two columns to the right; test: the edge of the `3` region on the `2` shape moves one column right).
    - The change is a set of cells, each recolored from one color to another; moved, it recolors a cell only where the cell holds the color it recolors from (test: the column the edge reaches recolors only its `2` cells).

## Rules
- `next-frame`: the output is one panel in size, and it is the last panel with the change applied once more, moved one more step past where it was last applied.

## Parameters
- `divider_color`: 5
- `panel_axis`: V
    - the axis along which the panels stack
- `divider_width`: 1

## Scene parameters
- `panel_count`: 4
