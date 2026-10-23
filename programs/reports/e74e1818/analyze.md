# e74e1818

## Concept
- Fits every pair (train0, train1, train2, test0) at the stored assignment `axis` = V, `bg` = 0, as `work/task/e74e1818/probe.py` shows.
- No witness has verdict `other`.
- On `repeated-color` (two 2 bands with a 3 band between them), the concept flips all the 2 cells over rows 1–5 as one layer, and the verdict is `$RowBandLayer`. That witness breaks the scene claim `stacked-layers`.
- Every layer in the evidence is mirror-symmetric about the grid's center column, and every input has distinct layer colors and a 0 frame. The concept statement does not need any of these, and the witnesses below break them.

## Choice points
- `layer`: what a layer is
    - `concept`: all the cells of one non-background color (`layer-per-color`)
    - `$RowBandLayer`: replaces `layer-per-color` and `stacked-layers`: a layer is a maximal run of consecutive lines whose non-background cells all have one color. It is undefined on an input where a line holds two non-background colors. Fits every pair. Witness `repeated-color`: it breaks `stacked-layers`, because the concept's 2 layer spans rows 1–5 around the 3 layer. It stands at the stored assignment, with plausibility `variant` and verdict `$RowBandLayer`. The invariant it breaks: the layers of every input have distinct colors.
    - `$ComponentLayer`: replaces `layer-per-color`: a layer is an 8-connected component of one color. Fails Fit at train1: the 5 cell at input (4,5) is its own component, so it stays at row 4, and the output has it at (6,5).
    - `$Component4Layer`: replaces `layer-per-color`: a layer is a 4-connected component of one color. Fails Fit at train0: the 2 cells at input (3,5) and (3,7) are their own components and stay at row 3, and the output has them at row 1.
    - `$ObjectLayer`: replaces `layer-per-color`: a layer is an 8-connected component of the non-background cells, whatever their colors. Fails Fit at train0: the whole picture is one object, so its flip reverses the layer order, and the output keeps the order.
- `layer-transform`: what moves each layer's cells
    - `concept`: reflection across the center of the layer's span along `axis` (`flip-in-span`)
    - `$Rot180InBox`: replaces `flip-in-span`: each layer turns a half turn within its bounding box. Fits every pair. Witness `asymmetric-layer`: it stands at the stored assignment and breaks no scene claim. Plausibility `variant`, verdict `concept`. The invariant it breaks: every layer is mirror-symmetric about the grid's center column.
    - `$Rot180InSpan`: replaces `flip-in-span`: each layer turns a half turn within its span of lines across the whole grid width. Fits every pair. Witness `off-center-layer`: it stands at the stored assignment and breaks no scene claim. Plausibility `variant`, verdict `concept`. The invariant it breaks: every layer's mirror axis is the grid's center column.
    - `$SwapEndLines`: replaces `flip-in-span`: the first and last lines of each span swap, and the inner lines stay. Fails Fit at test0: the 3 layer spans rows 4–7, and the output moves input row 5 to row 6 and row 6 to row 5.
- `bg`: the background color
    - `concept`: stored, 0
    - `bg=DominantColor`: derives `bg` as each commonest color of the input. Fits every pair. Witness `bg=DominantColor`: it stands at the stored assignment and breaks no scene claim. Color 3 has more cells than 0, so the branch takes 3 as the background, the flipped 0 cells collide with the 4 layer, and the branch is undefined there. Plausibility `borderline`, verdict `concept`. The invariant it breaks: 0 is the commonest color of every input, and the picture leaves a 0 frame on every side.
    - `bg=RarestColor`: derives `bg` as each rarest color of the input. Fails Fit at train0: the derivation gives 4, so the 0 cells form a layer and collide with the flipped cells, and the model is undefined.
    - `bg=SharedColor`: derives `bg` from the colors of the input alone, which gives every color of it. Fails Fit at train0: the model is undefined at the values other than 0.
- `layer` & `layer-transform`, `layer` & `bg`, `layer-transform` & `bg`: the two branches' changes applied together

## Open parameters
none

## Not formed
- A cyclic shift of the lines within each span: it agrees with the flip on 1- and 2-line spans and moves the middle line of a 3-line span. Every 3-line layer of train0 and train1 keeps its middle line in place, so no reader of the pairs takes it.
- A flip of the whole grid: it reverses the layer order, which every pair keeps. On each pair it gives `$ObjectLayer`'s output, and it fails Fit at train0 the same way.
- A derivation of `axis`: no proposer derives an axis from the input alone.
- `bg` by OutNewColor, AnyOutNewColor, VanishedColor, ChangedColor or UnchangedColor: in a run on one input, `ex_out` is empty, so each gives no value, and the branch is undefined on every pair.
- `bg` by the proposers of numbers, axes, boxes and D4 values, such as ScaleRatio: they derive no color.

## Tickets filed
none
