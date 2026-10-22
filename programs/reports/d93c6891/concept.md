# d93c6891

## Concept
- Gray bars lie along the border of a yellow field, and each bar touches an orange block that sits against that border. The bars are taken off the border and poured into the block they touch: the block turns gray layer by layer, from the border inward, one gray cell for each bar cell, and the rest of the block stays orange.

## Scene
- `field`: one rectangle of `floor` color, with the bars and blocks on it, on a `background` that fills the rest of the grid.
- `blocks`: rectangles of `block` color, each with one side on one side of the field's border, and that side of the field faces the background.
- `bars`: straight runs of `bar` color on the field's border, and each bar touches exactly one block.
- `whole-layers`: for each block, the count of bar cells that touch it is a whole multiple of the block's extent along its border side, and is at most the block's area.

## Rules
- `bar-count`: each block takes the total count of cells in the bars that touch it.
- `fill-from-border`: in each block, the layers parallel to its border side, starting at the border, turn `bar` color, as many layers as the count divided by the block's extent along the border; the other layers of the block keep `block` color.
- `bars-erase`: every bar cell turns `floor` color.
- `rest-unchanged`: every other cell keeps its input color.

## Parameters
- `bar`: 5
- `block`: 7
- `floor`: 4
- `background`: 0
    - the color outside the field, which tells which side of a block is on the field's border

## Scene parameters
none
