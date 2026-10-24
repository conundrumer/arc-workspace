# ecaa0ec1

## Concept
- A 3×3 tile has a pointer at one of its corners, and three marks stand around another corner; turn the tile, pointer and all, until the pointer reaches the marked corner, and wipe the marks.

## Scene
- `tile`: one 3×3 tile of `tile-colors` cells, the only cells that are neither `background` nor `marker`.
- `pointer`: one `marker` cell on the outward diagonal of one corner of the tile, `pointer-gap` cells out from the corner.
- `marks`: three `marker` cells around one other corner of the tile, each `mark-gap` cells out: one on the corner's outward diagonal, and one in line with each of the corner's two sides, past the tile on that side's axis.
- `no-other-marker`: the pointer and the three marks are the only `marker` cells.

## Rules
- `turn-tile`: the tile turns about its center by the rotation that takes the pointer's corner to the marked corner.
- `turn-pointer`: the pointer turns with the tile, so it lands `pointer-gap` cells out on the marked corner's diagonal.
- `wipe-marks`: the three marks become `background`; every other cell outside the tile and the turned pointer is `background`.

## Parameters
- `background`: 0
- `marker`: 4
    - the color of the pointer and of the marks
- `pointer-gap`: 1
    - the diagonal steps from the tile's corner to the pointer
- `mark-gap`: 2
    - the steps from the marked corner past the tile at which each mark stands, on the diagonal and on each side's line

## Scene parameters
- `tile-colors`: 1, 8
