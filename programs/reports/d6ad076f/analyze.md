# d6ad076f

## Concept
- The concept fits every train pair and the test pair at `bg` 0, `fill` 8, `inset` 1, and each of its claims has a relational form.
- No witness has the verdict `other`.
- The concept case is subsumed by `$EveryFacingPair`: the two models agree on every input with exactly two blocks, and the concept is undefined on the others.

## Choice points
- `bridge-span`: the extent of the bridge on the axis across the gap
    - `concept`: the overlap of the two blocks' spans, less `inset` lines at each end
    - `$NarrowerFace`: replaces `bridge`: the bridge's extent across the gap is the narrower block's span, less `inset` lines at each end; parameters `bg`, `fill`, `inset`; undefined where the two blocks' spans across the gap are equally wide. It fits every pair. Witness `staggered`: it breaks no scene claim, stands at the stored assignment, plausibility `variant`, verdict `concept`; it breaks the invariant that the narrower block's span across the gap lies within the wider block's span in every input.
    - `$NarrowerFaceClipped`: replaces `bridge`: the bridge's extent across the gap is the narrower block's span less `inset` lines at each end, cut to the overlap of the two spans; parameters `bg`, `fill`, `inset`; undefined where the two blocks' spans across the gap are equally wide. It fits every pair. Witness `staggered`: it breaks no scene claim, stands at the stored assignment, plausibility `variant`, verdict `concept`; it breaks the invariant that the narrower block's span across the gap lies within the wider block's span in every input.
- `block-count`: how many blocks the scene holds
    - `concept`: exactly two
    - `$EveryFacingPair`: replaces `two-blocks` with two or more solid rectangles of distinct colors on `bg`, and `bridge` with a bridge between each two rectangles that face each other across a gap of `bg`; parameters `bg`, `fill`, `inset`; undefined where no two rectangles face each other. It fits every pair. Witness `three-blocks`: it breaks `two-blocks`, stands at the stored assignment, plausibility `variant`, verdict `$EveryFacingPair`; it breaks the invariant that every input holds exactly two blocks.
- `bg`: where the field color comes from
    - `concept`: stored, 0
    - `bg=DominantColor`: the field color is derived as the commonest color of the input; parameters `fill`, `inset`; undefined where two colors tie for the most cells, and where the cells other than the derived color are not two solid rectangles that face each other. It fits every pair. Witness `bg=DominantColor`: it breaks no scene claim, stands at the stored assignment, plausibility `variant`, verdict `concept`; it breaks the invariant that 0 is the commonest color in every input.
    - `bg=SharedColor`: the field color is derived as each color the input holds; parameters `fill`, `inset`. It fails Fit at train0: on one input every color it holds is shared, so `bg` takes 0, 2 and 7 together, and at 2 the cells of 0 and 7 are no two facing rectangles.
- `fill`: where the bridge color comes from
    - `concept`: stored, 8
    - `fill=OutNewColor`: the bridge color is derived as a color in every train output and in no input; parameters `bg`, `inset`. It fails Fit at train0: `ex_out` is empty in a run on an input, so the derivation gives no value, and the model is undefined.
    - `fill=AnyOutNewColor`: the bridge color is derived as a color in some train output and in no input; parameters `bg`, `inset`. It fails Fit at train0, for the same reason.
- `separation-axis`: where the axis that separates the two blocks comes from
    - `concept`: read from each input, as the axis on which the two blocks' spans do not overlap
    - `$StoredAxis`: the separating axis is a stored value, and `facing-across-gap` and `bridge` read it; parameters `bg`, `fill`, `inset`, `axis`. It fails Fit: at the vertical axis it fails train1, and at the horizontal axis it fails train0.
- `bridge-span` & `block-count`, `bridge-span` & `bg`, `bridge-span` & `fill`, `bridge-span` & `separation-axis`, `block-count` & `bg`, `block-count` & `fill`, `block-count` & `separation-axis`, `bg` & `fill`, `bg` & `separation-axis`, `fill` & `separation-axis`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The bridge spans the overlap of the two blocks' interiors, each block less one line at each end: that overlap is the overlap of the blocks less one line at each end on every input, so its model is equivalent to the concept's.
- The bridge paints only the `bg` cells of the gap: wherever the concept or `$EveryFacingPair` is defined, the gap between two facing blocks holds only `bg`, so the two models are one.
- `inset` derived from the input: no proposer gives it, and no fact of the inputs alone or of the outputs alone fixes it.
- A bridge between blocks that face each other along a diagonal: no pair holds such blocks or a bridge off an axis, and the concept's `inset` has no reading along a diagonal.

## Tickets filed
- none
