# f3cdc58f

## Concept
- Count the cells of each color and draw the counts as a bar chart: one bar per color, standing on the bottom edge, in a fixed color order from the left.

## Scene
- `scattered-marks`: a grid on the `background` color holds single cells, each in one of the `palette` colors, scattered without structure.
- `counts-fit-height`: each palette color has at most as many cells as the grid has rows.

## Rules
- `bar-per-color`: the output has the input's size and is `background` everywhere except the bars.
- `bar-position`: the bar of the color at rank k in `bar_order` is the line k cells from the `start_side` edge, perpendicular to that edge.
- `bar-height`: the bar starts on the `base_side` edge and reaches as many cells into the grid as the input has cells of its color, painted in that color.

## Parameters
- `bar_order`: 1, 2, 3, 4
    - the palette colors in the order their bars stand, from the start side
- `base_side`: bottom
    - the edge the bars stand on
- `start_side`: left
    - the edge the first bar sits against, on the other axis from `base_side`
- `background`: 0

## Scene parameters
- `palette`: 1, 2, 3, 4
    - the colors the marks take
