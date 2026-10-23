# e7639916

## Concept
- A few scattered dots mark a rectangle: draw the outline of the smallest rectangle that holds every dot, and keep the dots on it.

## Scene
- `scattered-marks`: on a field of `background`, the input holds `mark-count` single cells of `mark-color`, and no two of them touch.

## Rules
- `bbox-outline`: each cell on the edge of the bounding box of the marks that is not a mark becomes `outline-color`.
- `keep-rest`: every other cell keeps its input color, so the marks stay on the outline and the inside of the box stays `background`.

## Parameters
- `background`: 0
- `outline-color`: 1

## Scene parameters
- `mark-count`: 3
- `mark-color`: 8
