# e21a174a

## Concept
- The concept fits every train and test pair. No witness has the verdict `other`. The rule in the concept file is the rule the generator applies, and it has a relational form: a layer's new band keeps its distance from the span's top edge equal to its old distance from the span's bottom edge, so the rule needs no approximation.
- Every input has one background line above the stack and one below it, and every layer is centered on one column. The concept states neither, and the `off-center`, `background=DominantColor` and `diagonal-stack` witnesses break them.

## Choice points
- `layer-unit`
    - `concept`: a layer is the color class of one non-background color (`color-layers`).
    - `$ColorComponent8`: replaces `color-layers`, so each 8-connected piece of one color is a layer. Parameters `background` and `stack_axis`. Undefined where two pieces share a line along `stack_axis`. Fits every pair. Witness `split-layer`, which breaks no scene claim. Plausibility `variant`, verdict `concept`. Invariant broken: every layer is 8-connected.
    - `$ColorComponent4`: replaces `color-layers`, so each 4-connected piece of one color is a layer. Parameters and undefined inputs are those of `$ColorComponent8`. Fails Fit at train1: the 3 cell at (8,6) touches the rest of its layer only at corners, so it becomes a layer of its own and moves above rows 6–7.
    - `$RowRuns`: replaces `color-layers`, so a layer is a maximal run of consecutive lines whose non-background cells all have one color. Parameters `background` and `stack_axis`. Undefined where a line holds two non-background colors. Fits every pair. Witness `repeated-color`, which breaks the scene claim `disjoint-bands`: color 2's band covers the line of color 1. Plausibility `variant`, verdict `$RowRuns`, the same output as `$ColorComponent8`. Invariant broken: every layer has a color of its own.
- `layer-content`
    - `concept`: each layer keeps its picture with no flip (`layer-kept`).
    - `$FlipLayers`: replaces `layer-kept`, so each layer is flipped along `stack_axis`. Parameters `background` and `stack_axis`. Undefined where the concept is undefined. Fails Fit at train0: the 4 layer must come out with its single cell above its bar (output rows 1–2), and the flip puts the bar on top.
- `arrangement`
    - `concept`: each band moves to its mirror image within the stack's span (`reverse-order`).
    - `$FrameMirror`: replaces `reverse-order`, so each band moves to its mirror image across the frame's middle line along `stack_axis`. Parameters `background` and `stack_axis`. Undefined where the concept is undefined. Fits every pair, because every stack in them is centered. Witness `off-center`, which breaks no scene claim. Plausibility `variant`, verdict `concept`. Invariant broken: the stack has one background line above it and one below it.
    - `$StoredColorOrder`: replaces `reverse-order`, so the layers come in the order that a stored ranking of the colors gives, packed in the span. Parameters `background`, `stack_axis` and `color_order`. Undefined where a layer's color has no rank. Fails Fit at train1: train0 needs 1 before 3 and train1 needs 3 before 1, so no ranking fits both.
- `background`
    - `concept`: the stored value 0.
    - `background=DominantColor`: derives `background` as the commonest color of the input. Where colors tie, it gives each of them. Undefined where the concept is undefined at the derived value. Fits every pair. Witness `background=DominantColor`, which breaks no scene claim at the stored assignment. Plausibility `borderline`, verdict `concept`. Invariants broken: 0 is the commonest color of every input, and the stack has a background line below it.
- `stack_axis`
    - `concept`: the stored value V.
    - `$AxisFromInput`: derives `stack_axis` as each axis along which the color layers' bands are disjoint. Undefined where no axis has disjoint bands. Fits every pair, because in every input one column crosses every layer, so only V is derived. Witness `diagonal-stack`, which breaks no scene claim. Plausibility `variant`, verdict `concept`. Invariant broken: one column crosses every layer.
- `layer-unit` & `layer-content`, `layer-unit` & `arrangement`, `layer-unit` & `background`, `layer-unit` & `stack_axis`, `layer-content` & `arrangement`, `layer-content` & `background`, `layer-content` & `stack_axis`, `arrangement` & `background`, `arrangement` & `stack_axis`, `background` & `stack_axis`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A layer drawn in more than one color: every layer touches the next one, so without color no reading of the pairs separates two neighboring layers.
- A layer that moves on the other axis, such as re-centering: no layer changes its columns in any pair, and a model that re-centers layers would add a rule that no pair shows.
- A cyclic shift of the layer order: train2 turns the order 1 2 3 into 3 2 1, which no cyclic shift gives.
- A flip of the whole frame: this is `$FlipLayers` & `$FrameMirror`, which fails Fit at train0.
- A derivation of `background` by `SharedColor`: on one input, `SharedColor` gives every color of that input, so the model gives more than one grid on train0 and fails Fit. `RarestColor` gives a layer color, and fails Fit at train0.

## Tickets filed
- none
