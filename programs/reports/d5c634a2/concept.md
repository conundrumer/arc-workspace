# d5c634a2

## Concept
- Count the T shapes whose stem points up and those whose stem points down, and tally each count as marks at the corners of its own 3×3 panel, filled column by column.

## Scene
- `t-shapes`: the input holds T tetrominoes of `shape_color` on a field of `0`, each a bar of three cells with a stem cell at the middle of one long side, and no two of them share an edge.
- `stem-directions`: each T's stem points toward one of `stem_dirs`.
- `fits-the-panel`: no more T shapes point toward one direction than a panel has corners.

## Rules
- `panel-per-direction`: the output is a grid of `0` made of two panels of `panel_size`, side by side along `panel_axis`, and each stem direction owns one panel, by `dir_panel`.
- `count-as-marks`: in the panel of a direction, the first n corners of the panel, in the order of `order_axis` and `order_corner`, take the mark color `dir_mark` of that direction, where n is the count of T shapes whose stem points that way.
- `same-slot-order`: both panels fill their corners in one order, at the same places relative to the panel.

## Parameters
- `dir_mark`: up → `3`, down → `1`
    - the mark color of each stem direction
- `dir_panel`: up → the first panel (cols 0–2), down → the second panel (cols 3–5)
- `panel_size`: 3×3
- `panel_axis`: H
- `order_axis`: H
    - the primary axis of the lexicographic order of the corners: column by column
- `order_corner`: TL
    - the corner the order runs from: left column first, top before bottom

## Scene parameters
- `shape_color`: `2`
- `stem_dirs`: up, down
