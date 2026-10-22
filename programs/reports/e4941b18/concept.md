# e4941b18

## Concept
- Two marks sit on top of a block. The one mark pushes the other along the block's top: the pushed mark rolls off the end of the block and falls to the floor beside it, and the pusher takes the cell the pushed mark left.

## Scene
- `background`: every cell that is not of the block or a mark has the color `background`.
- `block`: one solid rectangle of the color `block_color`, whose side toward `gravity` lies on the grid edge toward `gravity`.
- `marks-on-top`: one cell of `pusher_color` and one cell of `pushed_color` stand in the line next to the block on its side away from `gravity`, both within the block's extent across `gravity`.
- `room-to-fall`: the line next to the block's side toward which the pusher pushes lies inside the grid.

## Rules
- `pusher-takes-place`: the pusher's cell becomes `background`, and the pushed mark's cell becomes `pusher_color`.
- `pushed-falls-off`: the pushed mark moves in the direction from the pusher toward it, to the first cell past the end of the block, then falls toward `gravity` to the grid edge, where its cell becomes `pushed_color`.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `pusher_color`: `2`
- `pushed_color`: `8`
- `background`: `7`
- `block_color`: `5`
- `gravity`: bottom
    - the direction the pushed mark falls in

## Scene parameters
- none
