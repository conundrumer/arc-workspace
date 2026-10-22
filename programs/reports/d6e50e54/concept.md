# d6e50e54

## Concept
- The block is a magnet that turns on: each mark is pulled straight toward it, and comes to rest just outside it, unless the mark started closer to the block than the block's side length, in which case it is pulled one cell further, onto the block's near edge.

## Scene
- `one-square-block`: one solid square of `block_color` on a field of `bg`.
- `single-cell-marks`: one or more single cells of `mark_color`, each outside the block.
- `marks-in-line`: each mark lies in the block's rows or in the block's columns, so it faces exactly one side of the block.

## Rules
- `block-recolor`: every cell of the block becomes `fill_color`.
- `mark-cleared`: each mark's input cell becomes `bg`.
- `mark-pull`: a mark at distance d from the side it faces (d = 1 for a cell touching the block) moves toward the block along its line. When d is less than the block's side length, measured along the mark's line, the mark lands on the block's cell on that side, in the mark's line. Otherwise it lands on the cell just outside that side, in the mark's line.
- `mark-on-top`: a mark that lands on the block is drawn in `mark_color` over the fill.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `bg`: 7
- `block_color`: 1
- `fill_color`: 2
- `mark_color`: 9

## Scene parameters
none
