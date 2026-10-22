# bf89d739

## Concept
- Two dots sit on one line; join them with a straight trunk, then run a straight branch from every other dot square onto that trunk.

## Scene
- `scattered-dots`: single cells of `dot_color` lie apart on a field of `background`, no two touching.
- `one-aligned-pair`: exactly two dots share a row or a column, and no other two dots share a row or a column.
- `within-span`: every other dot lies off the pair's line, level with a cell strictly between the pair's two dots.

## Rules
- `trunk`: each cell strictly between the two aligned dots takes `line_color`.
- `branch`: for every other dot, each cell strictly between it and the trunk, on the perpendicular line through the dot, takes `line_color`.
- `keep`: every other cell keeps its input color.

## Parameters
- `background`: 0
- `line_color`: 3

## Scene parameters
- `dot_color`: 2
