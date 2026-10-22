# c0f76784

## Concept
- Each square outline gets its hole filled, and the fill color says how big the hole is.

## Scene
- `square-outlines`: the input holds several one-cell-thick square outlines of color `frame_color` on a field of `background`, each enclosing a square hole of `background` cells.
- `outlines-apart`: no two outlines touch, even at a corner.
- `hole-sizes-keyed`: the side of each hole is a key of `fill_by_side`.

## Rules
- `fill-hole-by-side`: each cell of an outline's hole takes the color that `fill_by_side` gives for that hole's side length.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `fill_by_side`: 1 → `6`, 2 → `7`, 3 → `8`
    - the fill color for each hole side length
- `background`: `0`

## Scene parameters
- `frame_color`: `5`
