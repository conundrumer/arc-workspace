# e872b94a

## Concept
- Count the gray snakes, and draw a one-cell-wide black strip one cell longer than that count.

## Scene
- `snakes-on-background`: the input holds `shape_color` paths on a `background` field, and no other color.
- `snakes-apart`: no two snakes touch, by a side or by a corner.

## Rules
- `count-snakes`: each part of the `shape_color` cells that is connected through shared sides is one snake.
- `strip-length`: the output is a strip along `axis`, `strip_width` cells wide, and as long as the snake count plus `extra_cells`.
- `strip-fill`: every cell of the strip is `fill_color`.

## Parameters
- `shape_color`: 5
- `fill_color`: 0
- `axis`: vertical
    - the axis the strip runs along
- `strip_width`: 1
- `extra_cells`: 1
    - the strip length less the snake count

## Scene parameters
- `background`: 0
