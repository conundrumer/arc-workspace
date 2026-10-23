# e9bb6954

## Concept
- Fits every train pair and the test pair. Each rule has a relational form: a block's center is the cell at equal distance from the block's two edges on each axis, and the rule needs no approximation.
- No witness has the verdict `other`.
- The concept's output is not the judged output on these witnesses:
    - `noise-touches-block` (verdict `$SquareOccurrence`, `variant`): a noise cell of the block's color touches the block, so that block is not a whole component.
    - `larger-block` (verdict `$AnySideSquare`, `variant`) and `mixed-block-sizes` (verdict `$AnySideSquare`, `borderline`): a block of side 5 is not found at the stored `block-size`.
    - `background=DominantColor` (verdict `background=DominantColor`, `variant`): on a field of 5, the stored `background` clears crossings to 0.
- The pairs fix `block-size` to 3: on train0, size 1 finds noise cells as blocks, and sizes 17 and 18 find no block. The pairs fix `background` to 0: every other color of train0 gives another output.

## Choice points
- `block-shape`: which components are blocks
    - `concept`: a solid square of side `block-size`
        - `block-size`: how the side is found
            - `concept`: stored, 3
            - `block-size=TileDim`: derived from the one input by TileDim, fails Fit at train0: the derived values include 1 and 3 as tile dims of an 18-cell axis, and at 1 every noise cell is a block, so the output holds more than one grid
            - `block-size=ConstInDim`: derived from the one input by ConstInDim, fails Fit at train0: at 17 and 18 no block is found, and the output is the input
    - `$AnySideSquare`: replaces `square-blocks` with a solid one-color square of any side above 1, with no `block-size`; undefined where such a square has an even side. Fits every pair. Witness `larger-block`, at the stored assignment, breaks `square-blocks`, `variant`, verdict `$AnySideSquare`; it breaks the invariant that every block is 3x3.
    - `$LargestComponents`: replaces `square-blocks` with the one-color components of the greatest cell count in the grid, crossed at the bounding box's center, with no `block-size`; undefined where such a bounding box has an even side. Fits every pair. Witness `mixed-block-sizes`, at the stored assignment, breaks `scattered-noise`, `borderline`, verdict `$AnySideSquare`; it breaks the invariant that all blocks of an input have one size.
- `block-grouping`: how a block's cells are grouped
    - `concept`: the one-color 4-connected component equals the square
    - `$Components8`: replaces the 4-adjacency in `square-blocks` with 8-adjacency, so a same-color cell at a block's corner joins it. Fits every pair. Witness `diagonal-noise-at-block`, at the stored assignment, breaks no scene claim, `ordinary`, verdict `concept`.
    - `$SquareOccurrence`: replaces `square-blocks` with every placement of a solid one-color square of side `block-size`, whether or not other cells of that color touch it; undefined where two placements of one color overlap. Fits every pair. Witness `noise-touches-block`, at the stored assignment, breaks `square-blocks`, `variant`, verdict `$SquareOccurrence`; it breaks the invariant that no noise cell of a block's color touches that block.
    - `$ColorBlind`: replaces `square-blocks` with components of all non-background cells, of any colors; fails Fit at train0: the noise 2 at (13,14) touches the 7 block, the two make a 10-cell component that is not a block, and (0,13) gives 0 where 7 is expected.
- `background`: how the background is found
    - `concept`: stored, 0
    - `background=DominantColor`: derived from the one input by DominantColor; undefined where two colors tie for the most cells. Fits every pair. Witness `background=DominantColor`, at the stored assignment, breaks `background-field`, `variant`, verdict `background=DominantColor`; it breaks the invariant that every input's field is 0.
    - `background=SharedColor`: derived from the one input by SharedColor, fails Fit at train0: every color of the input is derived, and each color other than 0 gives another output.
    - `background=RarestColor`: derived from the one input by RarestColor, fails Fit at train0: it derives 1, 3 and 5, and each gives another output.
- `crossing-color`: what a crossing cell takes
    - `concept`: `background`
    - `$CrossColorStored`: replaces `crossing-cleared` with a stored `cross-color`, 0. Fits every pair. Witness `crossings-at-new-background`, at `background` 5, breaks no scene claim at that assignment, `variant`, verdict `concept`; it breaks the invariant that every input's field is 0.
    - `$CrossKeepsInput`: replaces `crossing-cleared` with the input cell's color; fails Fit at train3: (15,4) gives 2 where 0 is expected.
    - `$CrossOverlay`: replaces `crossing-cleared` with one line's color drawn over the other's; fails Fit at train0: (5,13) gives 8 or 7 where 0 is expected.
- `crossing-test`: which cells count as crossings
    - `concept`: a cell on the lines of two different blocks
    - `$CrossOnlyPerpendicular`: replaces `crossing-cleared` with a cell where one block's row line meets another block's column line; undefined where two row lines or two column lines of different colors fall on one cell. Fits every pair, and fails Subsumption: wherever it is defined, its output is the concept's. Witness `shared-center-row`, at the stored assignment, on which the branch is undefined, breaks `separate-lines`, `borderline`, verdict `concept`; it breaks the invariant that the blocks of an input occupy pairwise disjoint row bands and column bands. No witness exists on which the branch is defined, because the two models differ only where lines coincide.
- `line-width`: how wide a line is
    - `concept`: one cell, the center row and the center column
    - `$BandLines`: replaces `center-cross` with lines as wide as the block; fails Fit at train0: (0,6) gives 8 where 0 is expected.
- `line-overwrite`: what a line paints over
    - `concept`: everything on its way, noise and other blocks
    - `$LinesStopAtNoise`: replaces `center-cross` with lines that stop before the first non-background cell outside the block; fails Fit at train0: (5,0) gives 0 where 8 is expected.
    - `$BlocksOverLines`: adds to `center-cross` that a cell of another block keeps that block's color. Fits every pair. Witness `line-through-block`, at the stored assignment, breaks `lines-miss-blocks`, `borderline`, verdict `concept`; it breaks the invariant that the blocks of an input occupy pairwise disjoint row bands and column bands.
- `noise`: what the noise becomes
    - `concept`: kept
    - `$DropNoise`: replaces `rest-kept` with noise cleared to `background`; fails Fit at train0: (0,8) gives 0 where 7 is expected.
- `block-shape` & `block-grouping`, `block-shape` & `background`, `block-shape` & `crossing-color`, `block-shape` & `crossing-test`, `block-shape` & `line-width`, `block-shape` & `line-overwrite`, `block-shape` & `noise`, `block-grouping` & `background`, `block-grouping` & `crossing-color`, `block-grouping` & `crossing-test`, `block-grouping` & `line-width`, `block-grouping` & `line-overwrite`, `block-grouping` & `noise`, `background` & `crossing-color`, `background` & `crossing-test`, `background` & `line-width`, `background` & `line-overwrite`, `background` & `noise`, `crossing-color` & `crossing-test`, `crossing-color` & `line-width`, `crossing-color` & `line-overwrite`, `crossing-color` & `noise`, `crossing-test` & `line-width`, `crossing-test` & `line-overwrite`, `crossing-test` & `noise`, `line-width` & `line-overwrite`, `line-width` & `noise`, `line-overwrite` & `noise`, `block-size` & `block-grouping`, `block-size` & `background`, `block-size` & `crossing-color`, `block-size` & `crossing-test`, `block-size` & `line-width`, `block-size` & `line-overwrite`, `block-size` & `noise`: the two branches' changes applied together

## Open parameters
none

## Not formed
- A block's center found other than as its middle cell: a 3x3 block has one middle cell, and every form of the center gives that cell.
- Lines that run only from the block to the edge: they cover the same cells as full-length lines through the center.

## Tickets filed
none
