# d968ffd4

## Concept
- Two blocks face each other from opposite ends of the grid, and each one spreads toward the other until they meet halfway. The spread fills whole lines across the grid, and when the gap has an odd number of lines, the middle line stays background.

## Scene
- `background`: one color fills every cell that is not in a block.
- `two-blocks`: there are two solid rectangular blocks, of two different colors that are not the background.
- `facing-ends`: the two blocks sit at the two opposite ends of one axis, each `margin` cells from its near edge of the frame, with background lines between them.
- `side-margin`: across the axis, each block spans the whole frame less `margin` cells at each side, so the two blocks have one extent across the axis.
- `thickness`: along the axis, each block is `block-thickness` lines thick.

## Rules
- `split-gap`: the lines between the two blocks split into two halves of equal count, and each half, the one nearer a block, takes that block's color on every cell of each of its lines, the side margins included.
- `odd-middle`: when the count of lines between the blocks is odd, the middle line keeps the background.
- `keep-rest`: every other cell keeps its input color.

## Parameters
- none

## Scene parameters
- `margin`: 1
    - the distance of each block from its near edge and from each side edge
- `block-thickness`: 2
    - the extent of each block along the axis on which the blocks face each other
