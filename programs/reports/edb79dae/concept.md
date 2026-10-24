# edb79dae

## Concept
- Cut out the framed board, and stamp each solid square on it with the stencil drawn in the square's color, repainted in the color that color's key says it becomes.

## Scene
- `background`: one background color fills the grid around every object.
- `frame`: one rectangle outline of `frame_color` encloses a field of background holding solid single-color squares, all of one size k, set apart by background.
- `keys`: outside the frame stand color keys, each a two-color block of `key_shape` in which the source color's half pokes one cell into the target color's half.
- `stencils`: outside the frame, each square color has one stencil: the cells of that color that belong to no key and lie outside the frame, whose bounding box is k by k.
- `one-key-per-color`: each square color is the source color of exactly one key.

## Rules
- `crop-frame`: the output is the frame's box, outline included.
- `stamp-stencil`: each square becomes its color's stencil, placed at the square by bounding box, with the stencil's cells in the target color of the key whose source is the square's color and the rest background.
- `keep-rest`: every other cell of the frame's box keeps its input color.

## Parameters
- `frame_color`: 5

## Scene parameters
- `key_shape`: the 3 by 4 block whose source color fills the two columns of one side and the middle cell of the third, the target color the rest
