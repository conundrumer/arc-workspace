# d93c6891

## Concept
- Fits every pair (`work/task/d93c6891/probe.py`). It has no witness with verdict `other`. Each rule counts or orders cells and layers that the task has, so the rules are the generator's rules as the concept file states them, and no rule is an approximation.
- The concept is undefined where a block's bar count is not a whole multiple of its extent along its border side, or is more than its area (`whole-layers`). The `remainder` and `overflow` points give the branches that are defined there.
- In every input, each bar runs from the block's border-side end along the field's border ring, and it turns at a field corner where it has to (train2 input (12,10)–(12,13) for the block at rows 10–11, cols 12–13). `$RingPath` reads that layout as the count source.

## Choice points
- `contact`: which bar cells a block takes
    - `concept`: every cell of each bar that 4-touches the block
    - `$SameSide`: replaces `bar-count`: the bar cells on the block's border-side line; parameters unchanged; undefined where the count on that line is not whole layers. Fails Fit at train0: the top block's line, row 4, holds 7 bar cells, (4,4) among them, and 7 is not a multiple of 3.
    - `$Contact8`: replaces `bar-count`: every cell of each bar that touches the block at a side or a corner; parameters unchanged; undefined where the concept is. Fits every pair. Witness `diagonal-bar`: breaks `bars` (the bottom bar touches no block), stands at the stored assignment, `borderline`, verdict `concept`. Invariant broken: every bar 4-touches a block.
    - `$RingPath`: replaces `bar-count`: the bar cells that a walk along the field's border ring reaches from the block's own ring cells, through bar cells; parameters unchanged; undefined where the concept is. Fits every pair. Witness `bar-under-block`: breaks no scene claim, stands at the stored assignment, `borderline`, verdict `concept`. Invariant broken: every bar meets its block at a cell on the border ring.
- `quantity`: what of the taken bars sets the number of layers
    - `concept`: the count of bar cells divided by the block's extent along its border side
    - `$PerBar`: replaces `fill-from-border`: one layer for each bar that touches the block; parameters unchanged; undefined where that number is more than the block's depth. Fails Fit at train0: the left block (rows 10–12, cols 4–6) takes one bar and the output fills two columns.
- `fill-side`: the side the layers start from
    - `concept`: the block's side on the field's border
    - `$FromContact`: replaces `fill-from-border`: the block side that the bars touch; parameters unchanged; undefined where bars touch two sides. Fails Fit at train0: the left block's bar touches its top side, so rows 10–11 fill, and the output fills cols 4–5.
    - `$FromBarLine`: replaces `fill-from-border`: the layers run parallel to the touching bars' line and start at the block side nearest that line, and a one-cell bar takes the border side; parameters unchanged; undefined where the touching bars lie on two crossing lines. Fits every pair. Witness `bottom-bar-right-block`: breaks no scene claim, stands at the stored assignment, `ordinary`, verdict `concept`.
    - `$Inner`: replaces `fill-from-border`: the side opposite the border side; parameters unchanged; undefined where the concept is. Fails Fit at train0: the left block fills cols 5–6, and the output fills cols 4–5.
- `remainder`: a bar count that is not a whole multiple of the block's extent along its border side
    - `concept`: undefined
    - `$FloorLayers`: replaces `fill-from-border` and drops part of `whole-layers`: the whole layers the count gives fill, and the cells left over are dropped; parameters unchanged; defined where the count is not a multiple. Fits every pair. Witness `partial-layer`: breaks `whole-layers`, stands at the stored assignment, `foreign`, verdict `$PartialFromBar`. Invariant broken: each block's bar count is a whole multiple of its extent along its border side.
    - `$PartialFromBar`: replaces `fill-from-border` and drops part of `whole-layers`: the whole layers fill, and the cells left over fill the next layer from the block end that the bars touch; parameters unchanged; undefined where a remainder is left and bars touch both ends. Fits every pair. Witness `partial-layer`: breaks `whole-layers`, stands at the stored assignment, `foreign`, verdict `$PartialFromBar`. Invariant broken: the same as for `$FloorLayers`.
- `overflow`: a bar count of more than the block's area
    - `concept`: undefined
    - `$CapAtBlock`: replaces `fill-from-border` and drops part of `whole-layers`: the whole block fills, and the extra bar cells are erased with the rest; parameters unchanged; defined there. Fits every pair. Witness `overfull`: breaks `whole-layers`, stands at the stored assignment, `foreign`, verdict `$CapAtBlock`. Invariant broken: each block's bar count is at most its area.
- `loose-bars`: a bar that touches no block
    - `concept`: it turns `floor` color
    - `$KeepLoose`: replaces `bars-erase`: only the bars that a block takes turn `floor` color, and the others keep `bar` color; parameters unchanged; undefined where the concept is. Fits every pair. Witness `loose-bar`: breaks `bars`, stands at the stored assignment, `borderline`, verdict `concept`. Invariant broken: every bar touches a block.
- `field`: the cells that make up the field, which give each block's border side
    - `concept`: the cells that are not `background` color
    - `$FieldByColors`: replaces the field of `fill-from-border`: the cells of `floor`, `bar` or `block` color; drops the parameter `background`; undefined where a block has other than one side that faces no field cell. Fits every pair. Witness `stray-color-row`: breaks `field`, stands at the stored assignment, `borderline`, verdict `concept`. Invariant broken: the inputs hold no colors other than 0, 4, 5 and 7.
- `bar`: how the bar color is given
    - `concept`: stored, 5
    - `bar=RarestColor`: the input's least common colors; undefined where it gives none. Fails Fit at train1: 5 and 7 tie at 6 cells, so the output holds two grids.
    - `bar=DominantColor`: fails Fit at train0, where it gives 4.
    - `bar=SharedColor`, `bar=VanishedColor`: with `ex_out` empty both give every color of the input, so they are one model. Fails Fit at train0.
    - `bar=OutNewColor`, `bar=AnyOutNewColor`, `bar=ChangedColor`, `bar=UnchangedColor`: give no value with `ex_out` empty, so they are undefined on every input. Fail Fit at train0.
- `block`: how the block color is given
    - `concept`: stored, 7
    - `block=RarestColor`: fails Fit at train0, where it gives 5.
    - `block=DominantColor`: fails Fit at train0, where it gives 4.
    - `block=SharedColor`, `block=VanishedColor`: one model, as for `bar`. Fails Fit at train0.
    - `block=OutNewColor`, `block=AnyOutNewColor`, `block=ChangedColor`, `block=UnchangedColor`: undefined on every input. Fail Fit at train0.
- `floor`: how the floor color is given
    - `concept`: stored, 4
    - `floor=DominantColor`: fails Fit at train2, where 0 has 130 cells and 4 has 96.
    - `floor=RarestColor`: fails Fit at train0, where it gives 5.
    - `floor=SharedColor`, `floor=VanishedColor`: one model, as for `bar`. Fails Fit at train0.
    - `floor=OutNewColor`, `floor=AnyOutNewColor`, `floor=ChangedColor`, `floor=UnchangedColor`: undefined on every input. Fail Fit at train0.
- `background`: how the background color is given
    - `concept`: stored, 0
    - `background=DominantColor`: fails Fit at train0, where 4 has 117 cells and 0 has 112.
    - `background=RarestColor`: fails Fit at train0, where it gives 5.
    - `background=SharedColor`, `background=VanishedColor`: one model, as for `bar`. Fails Fit at train0.
    - `background=OutNewColor`, `background=AnyOutNewColor`, `background=ChangedColor`, `background=UnchangedColor`: undefined on every input. Fail Fit at train0.
- `contact` & `quantity`, `contact` & `fill-side`, `contact` & `remainder`, `contact` & `overflow`, `contact` & `loose-bars`, `contact` & `field`, `contact` & `bar`, `contact` & `block`, `contact` & `floor`, `contact` & `background`, `quantity` & `fill-side`, `quantity` & `overflow`, `quantity` & `loose-bars`, `quantity` & `field`, `quantity` & `bar`, `quantity` & `block`, `quantity` & `floor`, `quantity` & `background`, `fill-side` & `remainder`, `fill-side` & `overflow`, `fill-side` & `loose-bars`, `fill-side` & `bar`, `fill-side` & `block`, `fill-side` & `floor`, `remainder` & `overflow`, `remainder` & `loose-bars`, `remainder` & `field`, `remainder` & `bar`, `remainder` & `block`, `remainder` & `floor`, `remainder` & `background`, `overflow` & `loose-bars`, `overflow` & `field`, `overflow` & `bar`, `overflow` & `block`, `overflow` & `floor`, `overflow` & `background`, `loose-bars` & `field`, `loose-bars` & `bar`, `loose-bars` & `block`, `loose-bars` & `floor`, `loose-bars` & `background`, `field` & `bar`, `field` & `block`, `field` & `floor`, `bar` & `block`, `bar` & `floor`, `bar` & `background`, `block` & `floor`, `block` & `background`, `floor` & `background`: the two branches' changes applied together
- `quantity` & `remainder`: `$PerBar`'s model alone, for each `remainder` branch, as a count of bars leaves no remainder
- `fill-side` & `field`: the two branches' changes applied together
    - `$FromContact` & `$FieldByColors`: `$FromContact`'s model alone, as `$FromContact` reads no border side
- `fill-side` & `background`: the two branches' changes applied together
    - `$FromContact` & each `background` derivation: `$FromContact`'s model alone, as `$FromContact` reads no border side and so no `background`
- `field` & `background`: `$FieldByColors`'s model alone, for each `background` derivation, as `$FieldByColors` reads no `background`

## Open parameters
none

## Not formed
- The bars slide along their line into the block: train0's top block takes two 3-cell bars and fills two rows, so the slid cells have to stack into layers. Stacked from the border, they give the concept's output wherever the count fills whole layers, and `$PartialFromBar` gives the partial layer.
- A fill color of its own: the filled cells take the bar color in every pair, and that value follows from `bar` in every variant task, so it is derived data.
- `ChangedPairs` and `VanishedNewPairs` derivations: no parameter of the concept is a pair of colors.
- A bar that touches two blocks split between them: no input has such a bar, and no reading of the pairs gives a way to split it. The concept counts it for each block.

## Tickets filed
- 10-760_task_d93c6891_analyze.md
