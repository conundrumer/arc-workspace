# dd6b8c4b

## Concept
- Loose marks walk through the gaps in the walls into a square box, nearest first; each mark that gets in leaves its place empty, and the box fills up in reading order until it is full.

## Scene
- `field`: a grid of `background` with `wall` cells drawn on it.
- `box`: one `box_size` square of `box_color` cells with a `center_color` cell at its center.
- `marks`: single `mark` cells scattered over the field, some of them shut off from the box by walls.

## Rules
- `reach`: a mark reaches the box when a 4-adjacent walk through cells that are not `wall` joins it to a box cell; its distance is the length of the shortest such walk.
- `take`: the reached marks are taken nearest first, as many as the box has cells, or all of them when there are fewer.
- `vacate`: each taken mark becomes `background`.
- `fill`: the box cells, the center included, take `mark` in `fill_order`, one for each taken mark.
- `keep`: every other cell keeps its input color.

## Parameters
- `background`: 7
- `wall`: 6
- `mark`: 9
- `box_color`: 3
- `center_color`: 2
- `fill_order`: reading order, rows from the top, each row from the left
    - the order in which the box cells fill: a start corner (top-left) and a primary axis (along rows)

## Scene parameters
- `box_size`: 3×3
