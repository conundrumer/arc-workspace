# d43fd935

## Concept
- Fits every pair (train0–train2, test0). Every claim has a relational form: a `Ray` cast from each non-background, non-block cell toward the four cardinals, stopped by the block's cells, paints its clear cells in the caster's color.
- No witness has verdict `other`.
- The concept is undefined where two dots of different colors lie on one line on the same side of the block (`two-color-stack`), since the far dot's line covers the near dot and its line; `$PaintToDot` gives the verdict there.
- Where the concept is defined, `$PaintToDot` gives the same output.

## Choice points
- `stopper`: which cells stop a dot's line
    - `concept`: the block's own cells
    - `$Box`: the cells of the block's bounding box stop the line; replaces `ray-to-block`; no parameter; defined wherever the concept is. Fits every pair. Witness `l-block`: an L-shaped block of three cells with a dot level with the empty corner. It breaks `one-block` (the block is a solid 2×2 square in every input). Plausibility `borderline`, verdict `concept`.
- `obstacle`: what a line does at a non-background cell between its dot and the block
    - `concept`: it paints over that cell and runs on to the block
    - `$StopAtDot`: every non-background cell blocks a line, and a dot casts only where the first cell it meets is a block cell; replaces `ray-to-block`; no parameter; defined wherever two lines do not paint one cell in different colors. Fits every pair. Witness `stacked-dots`: two dots of one color on one row on the same side of the block. It breaks `clear-paths` (no input has a non-background cell between a level dot and the block). Plausibility `borderline`, verdict `concept`.
    - `$PaintToDot`: a dot level with the block paints up to the first non-background cell on its line, whatever that cell is; replaces `ray-to-block`; no parameter; defined wherever two lines do not paint one cell in different colors. Fits every pair. Witness `two-color-stack`: dots of colors 1 and 8 on one row on the same side of the block, where the concept is undefined. It breaks `clear-paths` (no input has a non-background cell between a level dot and the block). Plausibility `borderline`, verdict `$PaintToDot`.
- `casters`: which cells cast a line
    - `concept`: every non-background cell outside the block
    - `$SingletonsOnly`: only the cells that form a one-cell 4-connected object of their own; replaces `ray-to-block`; no parameter; defined wherever the concept is. Fits every pair. Witness `domino-caster`: a two-cell object of color 1 level with the block. It breaks `single-dots` (every non-block object in every input is one cell). Plausibility `borderline`, verdict `concept`.
- `block`: how the block is found
    - `concept`: the cells of the stored `block_color`
    - `$BlockByShape`: the block is the one 4-connected non-background object larger than one cell, of any color; replaces `one-block` and drops `block_color`; undefined on an input with no such object or more than one. Fits every pair. Witness `other-color-block`: a 2×2 block of color 4. It breaks `one-block` (`block_color` is 3, and every input's block is color 3). Plausibility `borderline`, verdict `$BlockByShape`.
- `background`: where the background color comes from
    - `concept`: stored `background`
    - `background=DominantColor`: `background` is the commonest color of the input; replaces `one-block`'s stored background; on a tie, each tied color runs. Fits every pair. Witness `background=DominantColor`: a field of 5 with the block and two dots, where the concept is undefined. It breaks `one-block` (`background` is 0, and every input's field is 0). Plausibility `borderline`, verdict `background=DominantColor`.
- `directions`: the directions a dot casts in
    - `concept`: the four cardinals
    - `$Diagonal`: the four diagonals as well; replaces `ray-to-block`; no parameter. Fails Fit at train0: the dot at (7,6) lies on the diagonal of block cell (4,3), and the branch paints (5,4) and (6,5), which the output keeps 0.
- `stopper` & `obstacle`, `stopper` & `casters`, `stopper` & `block`, `stopper` & `background`, `stopper` & `directions`, `obstacle` & `casters`, `obstacle` & `block`, `obstacle` & `background`, `obstacle` & `directions`, `casters` & `block`, `casters` & `background`, `casters` & `directions`, `block` & `background`, `block` & `directions`, `background` & `directions`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Dots not level with the block cast to the grid edge: train0 keeps (0,0), (6,7), (7,6) and (9,4) with no line, so no reading of the pairs gives it.
- The line takes a fixed color: train1 paints lines of 7 and of 8, each in its dot's color, so no reading of the pairs gives it.
- The block sends lines out to the dots: it paints the same cells as the concept on every input, so it is the concept's model.
- The block is the 2×2 square of `block_color`: `block_size` is a scene parameter the program does not read, and `$BlockByShape` already forms the reading that finds the block by shape.

## Tickets filed
- 10-696_task_d43fd935_analyze.md
- 10-697_task_d43fd935_analyze.md
