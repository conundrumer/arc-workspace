# ff805c23

## Concept
- Fits every pair (train0–2, test0), and the test output is the one grid it gives. The checks after the concept found the following.
    - Every input's visible cells are symmetric under the whole of D4 about the grid center, not just under the two midline mirrors. So the concept case runs every value of `symmetry` (SYM_BOX, SYM_D4), and both values give the same outputs on every pair. The case is undefined on an input where those values give different outputs.
    - Every input is 24×24 (`grid_size`, a scene parameter now in `square-grid`), and every mask is 5×5 of color 1. Each pattern color has at least 89 cells, against the mask's 25.
    - The mask's left-right image overlaps the mask in train2 and test0, and its top-bottom image does in train1. So no single mirror restores every pair, while each group holding the half turn does.
- No witness has verdict `other`.
- The generator's rule, as it applies it: draw a 24×24 pattern symmetric about its center, paint a solid 5×5 block of 1 where some symmetric copy of every covered cell stays visible, and output the covered content. `crop-mask` and `restore-by-symmetry` state that rule exactly, with no approximation.

## Choice points
- `mask-color`: how the mask color is determined
    - `concept`: stored, `mask_color` = 1
    - `mask_color=RarestColor`: replaces the stored value in `solid-mask`. `mask_color` takes each color of lowest count in the input. No parameter. Undefined where a color rarer than the mask, or one tied with it, has no visible image, and where the concept is undefined. Fits every pair. Witness `mask_color=RarestColor`: the 5×5 block is color 7 and no cell is 1. It breaks `solid-mask` (`mask_color`) and stands at the stored assignment. Plausibility `variant`, verdict `mask_color=RarestColor`. It breaks the invariant that the mask is color 1 in every input.
    - `$MaskBySolidBlock`: replaces the stored value in `solid-mask`. The clauses derive `mask_color` as each color whose cells form one solid rectangle. No parameter. Undefined where no color's cells form one, and where the concept is undefined. Fits every pair. Witness `mask-recolored-sparse-pattern`: the block is color 7, beside a pattern color 4 of 8 cells. It breaks `solid-mask` (`mask_color`) and stands at the stored assignment. Plausibility `variant`, verdict `$MaskBySolidBlock`. It breaks two invariants: the mask is color 1, and every pattern color has more cells than the mask.
    - `mask_color=DominantColor`: `mask_color` is each color of highest count. Fails Fit at train0, where it takes 2 and is undefined.
    - `mask_color=SharedColor`: on one input it gives every color, so no cell is visible. Fails Fit at train0, undefined.
    - `mask_color=VanishedColor`: with no outputs read, it gives every color of the input. Fails Fit at train0, undefined.
- `restoration`: how a masked cell's content follows from its images
    - `concept`: each masked cell takes the one color its visible images under `symmetry` share. Undefined where they disagree or where there is none.
    - `$BlockImage`: replaces `restore-by-symmetry`. The output is each image of the mask's box, under an element of `symmetry`, that holds no mask cell, read back through that element. No parameter. Undefined where every image box holds a mask cell. Fits every pair. Witness `broken-symmetry-two-copies`: train1 with (14,16) changed to 8, in the left-right copy of the block. It breaks `symmetric-pattern` and stands at the stored assignment. Plausibility `foreign`, verdict `$ModeImage`. It breaks the invariant that every input is exactly symmetric under D4 about its center.
    - `$ModeImage`: replaces `restore-by-symmetry`. Each masked cell takes the commonest color among its visible images, through the lib's `Mode`. No parameter. Undefined where a masked cell has no visible image, or where two colors tie as commonest. Fits every pair. Witness `broken-symmetry-two-copies`, as for `$BlockImage`, verdict `$ModeImage`.
    - `$BlockTranslate`: copies the image box of the mask's box without reflecting it. Fails Fit at train0, where it gives 6 grids and none is the output.
- `symmetry-center`: the center the group acts about
    - `concept`: the grid's center, derived from the frame
    - `$StoredCenter`: replaces the center in `symmetric-pattern` with a stored `center` (row sum 23, column sum 23). Undefined where some masked cell has no visible in-frame image about that center, or where its images disagree. Fits every pair. Witness `$StoredCenter`: train1 padded with two rows and two columns of 0 at the bottom and right, giving 26×26. It breaks `square-grid` (`grid_size`) and `symmetric-pattern`, and stands at the stored assignment. Plausibility `foreign`, verdict `$StoredCenter`. It breaks the invariant that the pattern fills a 24×24 grid, centered.
    - `$FoundCenter`: replaces the center in `symmetric-pattern`. The clauses take each center at which every visible cell agrees with its visible in-frame images and every masked cell has one, and the output holds each center's restoration. No parameter. Undefined where no center qualifies. Fits every pair: the degenerate edge centers it also finds give the same output. Witness `off-center-pattern`: train1 padded with two rows and two columns of 0 at the top and left, giving 26×26. It breaks `square-grid` (`grid_size`) and `symmetric-pattern`, and stands at the stored assignment. Plausibility `foreign`, verdict `$FoundCenter`. It breaks the same invariant as `$StoredCenter`'s witness.
- `output-frame`: the output's frame
    - `concept`: the mask's bounding box, derived
    - `$StoredOutSize`: replaces `crop-mask` with a stored `out_size` 5×5. The output is each window of that size that holds every mask cell, restored. Undefined where no such window exists. Fits every pair. Witness `$StoredOutSize`: train0 with a 5×4 mask (rows 0–4, cols 18–21). It breaks `solid-mask` (`mask_size`) and stands at the stored assignment. Plausibility `variant`, verdict `concept`. It breaks the invariant that every mask is 5×5.
- `mask-color` & `restoration`, `mask-color` & `symmetry-center`, `mask-color` & `output-frame`, `restoration` & `symmetry-center`, `restoration` & `output-frame`, `symmetry-center` & `output-frame`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `symmetry` as SYM_LR or SYM_TB alone: the pairs separate them. SYM_LR is undefined on train2 and SYM_TB on train1, where the mirror image overlaps the mask.
- `symmetry` as SYM_HT, SYM_C4 or SYM_X: each fits every pair, but none holds the mirrors across both midlines that the concept's "mirror-symmetric" names, so a reader of the concept does not take them as values of `symmetry`.
- `mask_color` by ChangedColor, UnchangedColor, OutNewColor or AnyOutNewColor: these proposers read train outputs, and under `@derive` a proposer reads no output. Read from the outputs instead, the determination gives the stored value, which is the concept branch.
- A mirror tried before the others (left-right first, say): it singles out one member of an orientation type that the task does not distinguish, and no source gives it.
- The output size from ConstOutDim (5): this is `$StoredOutSize`.

## Tickets filed
- none
