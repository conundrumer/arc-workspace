# c3fa4749

## Concept
- Fits every pair (`probe.py`), with `min_block_cells` anywhere from 6 to 23; at 24 the 23-cell block of train1 drops out and train1 fails.
- Witness `block-colored-channel-cell`: plausibility `ordinary`, verdict `other`. A channel cell whose random color is the block's color joins the block region and cuts the channel, and the generator fills the whole channel all the same; train2 input (4,4) is one such cell, walled in by the channel, which the concept fills.
- The rule as the generator applies it: the generator draws a 4-connected channel from one cell of the grid border into a block, puts the grid's paint color on that border cell and random colors on the rest, and fills the channel with the paint when it ends inside the block. A channel that runs out through the block's side is left as it is. `dead-end-fills` takes the pockets of non-block cells in place of the drawn channel, and so misses any drawn cell whose random color is the block's.

## Choice points
- `mouth-place`: where a dead end's mouth lies
    - `concept`: the pocket's one opening is a cell on the grid border, and every other neighbor of the pocket lies in one block region
    - `$MouthOnBlockSide`: replaces `dead-end-fills`. Pockets are the 4-connected sets of cells inside a block region's bounding box that lie outside that region, and a pocket with exactly one cell on that box's edge takes that cell's color. Its parameter is `min_block_cells`, and it is defined on every input. It fits every pair. Witness `interior-block` breaks scene claim `blocks` (a block stands clear of the grid border). Plausibility `variant`, verdict `$MouthOnBlockSide`.
- `adjacency`: the adjacency of block regions, pockets and their walls
    - `concept`: 4-adjacency
    - `$Adjacency8`: replaces `dead-end-fills` and `blocks` with 8-adjacency, and keeps the rest. Its parameter is `min_block_cells`, and it is defined on every input. It fits every pair. Witness `diagonal-step` breaks no scene claim. It breaks the invariant that every channel is 4-connected. Plausibility `borderline`, verdict `$Adjacency8`.
- `mouth-count`: how many border cells a dead end meets
    - `concept`: exactly one
    - `$WalledAnyMouth`: replaces `dead-end-fills`. A walled pocket that meets the grid border at one or more cells, all of one color, takes that color, and a pocket whose border cells differ is kept. Its parameter is `min_block_cells`, and it is defined on every input. It fits every pair. Witness `two-cell-mouth` breaks no scene claim. It breaks the invariant that every channel meets the grid border at one cell. Plausibility `borderline`, verdict `$WalledAnyMouth`.
- `leak`: what a channel that runs out through a block's side does
    - `concept`: it is kept
    - `$LeakyFills`: replaces `dead-end-fills`. A channel that enters a block from the grid border takes the color of its border cell, whether or not it runs out through the block's side. Its parameter is `min_block_cells`. It fails Fit at train1: input row 12 cols 14–19 and col 14 rows 13–17 would take 4, and the output keeps them.
- `walled-block-cells`: whether the block-colored cells a dead end walls in fill
    - `concept`: they fill, as cells of the pocket
    - `$KeepBlockColored`: replaces `dead-end-fills`. Only the cells of a pocket that are not of the block's color fill. Its parameter is `min_block_cells`. It fails Fit at train2: input (4,4) is 7, and the output gives 8.
- `fill-color`: where the fill color comes from
    - `concept`: derived as the color of the pocket's border cell
    - `$StoredPaint`: replaces `dead-end-fills` with one stored fill color for the task. Its parameters are `min_block_cells` and `fill_color`. It fails Fit at train1: train0 needs 9 and train1 needs 4.
- `mouth-place` & `adjacency`, `mouth-place` & `mouth-count`, `mouth-place` & `leak`, `mouth-place` & `walled-block-cells`, `mouth-place` & `fill-color`, `adjacency` & `mouth-count`, `adjacency` & `leak`, `adjacency` & `walled-block-cells`, `adjacency` & `fill-color`, `mouth-count` & `leak`, `mouth-count` & `walled-block-cells`, `mouth-count` & `fill-color`, `leak` & `walled-block-cells`, `leak` & `fill-color`, `walled-block-cells` & `fill-color`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Other values of `min_block_cells`: every value from 6 to 23 fits the pairs. The value only sets a block apart from the field's one-color clumps, which reach 6 cells in test0. A reader of the concept takes no count from it, so no value is an open value.
- The fill color as the color of the channel's inner end: fails train0, where row 13 ends at (13,7) = 2 and the fill is 9.
- The fill color as the commonest color in the channel: fails train0, where the channel at col 16–17 holds four 5s and the fill is 9.

## Tickets filed
- 10-503_task_c3fa4749_analyze.md
