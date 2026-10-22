# b4a43f3b

## Concept
- Fits every pair (`work/task/b4a43f3b/check_concept.py`, `work/task/b4a43f3b/probe.py`). Each claim has a relational form: the halves, the block read-down, the tile cut and the stamp are each cells joined by position.
- No witness has the verdict `other`.
- The concept is undefined where the half on `pattern_side` is not in `pattern_scale`×`pattern_scale` blocks, or where the grid has no middle line. Witnesses `picture-below`, `picture-in-3-blocks` and `short-mask` show this, and in each one a branch gives the output a person reads.

## Choice points
- `picture-side`
    - `concept`: the picture is the half on the stored `pattern_side` (top)
    - `$PictureByBlocks`: replaces `picture-down`. The picture is the half that is in `pattern_scale`×`pattern_scale` blocks, and the mask is the other half. Undefined where both halves or neither half is in blocks. Fits every pair. Witness `picture-below`: train0 flipped top to bottom. It breaks `scaled-picture` (the picture is not on `pattern_side`). Stored assignment, `variant`, verdict `$PictureByBlocks` (the group of `$PictureByBlocks` and `$PictureByColors`). A second witness, `mask-in-blocks`, has a mask in aligned 2×2 blocks. It is undefined there and `$PictureByColors` is not, and it is `borderline` (no mask in the evidence is in aligned blocks), verdict `concept`.
    - `$PictureByColors`: replaces `picture-down`. The mask is the half whose non-`background` cells have one color, and the picture is the other half. Undefined where both halves or neither half has one color. Fits every pair. Witness `picture-below`, as above: stored assignment, `variant`, verdict `$PictureByColors`, which is in the same group as `$PictureByBlocks`. On `solid-picture` it is undefined.
- `picture-scale`
    - `concept`: the stored `pattern_scale` (2)
    - `$ScaleFromBlocks`: replaces `picture-down`. The scale is derived as the largest side k such that the picture half is in aligned k×k blocks. Defined on every input. Fits every pair. Witness `solid-picture`: train0 with every picture-half cell 1. The branch reads a 1×1 picture and gives the 6×6 mask in 1, and the concept gives 18×18. It breaks no scene claim. Stored assignment, `borderline` (it breaks the invariant that every picture has at least two colors, a `background` cell among them), verdict `concept`.
    - `$StoredPictureExtent`: replaces `picture-down`. A stored picture extent (3) takes the place of `pattern_scale`, and the scale is derived as `half_extent` / 3. Undefined where the half extent is not a multiple of 3. Fits every pair. Witness `picture-in-3-blocks`: 9×9 halves with the picture in 3×3 blocks. The concept is undefined there, and the branch gives 27×27. It breaks `half-extent` and `scaled-picture`. Stored assignment, `variant`, verdict `$StoredPictureExtent` (the group of `$StoredPictureExtent` and `$ScaleFromBlocks`).
- `marked-cells`
    - `concept`: a mask cell is marked when it is not `background`
    - `$MarkByColor`: replaces `stamp-at-marks`. A mask cell is marked when it is `mask_color`, which moves to Parameters (2). Fits every pair. Witness `mask-color-4`: train3 with its mask in 4, a color permutation of train3. It breaks `mask` (mask cells are `mask_color`). Stored assignment, `variant`, verdict `concept`. The branch gives an all-0 output.
- `halves`
    - `concept`: the halves are the rows on each side of the middle line
    - `$SplitAtSeparator`: replaces `two-halves` (scene claim) and the split that `picture-down` reads. The halves are the rows on each side of the one full row of `separator_color`, which moves to Parameters (5). Undefined where no such row or several exist. Fits every pair. Witness `short-mask`: train0 without its last two rows. The concept is undefined there, and the branch gives 12×18. It breaks `two-halves` (equal halves) and `half-extent`. Stored assignment, `variant`, verdict `$SplitAtSeparator`.
        - `separator`: under `$SplitAtSeparator`
            - `concept`: the stored `separator_color`
            - `$SeparatorAnyLine`: the separator is the one full row of a single non-`background` color, and the branch is undefined where several such rows exist. It fails Fit at train3 (rows 4–5 are full rows of 3) and at test0 (row 9 is a full row of 2).
- `background`
    - `concept`: the stored `background` (0)
    - `background=DominantColor`: `@derive` of `background` by DominantColor on the input. Fits every pair. Witness `background=DominantColor`: train3's picture over a mask that marks 30 of its 36 cells. It breaks no scene claim. Stored assignment, `borderline` (it breaks the invariant that 0 is the commonest color of every input, since every mask in the evidence marks at most 13 cells), verdict `concept`.
- `stamp-colors`
    - `concept`: a stamped cell takes the picture cell's color
    - `$StampInMaskColor`: the picture's non-`background` cells are drawn in the marked mask cell's color. It fails Fit at train0.
- `stamp-sites`
    - `concept`: the picture is stamped at the cells of the other half
    - `$SelfFractal`: the picture is stamped at its own non-`background` cells, and the mask is not read. It fails Fit at train0 (9×9 against 18×18).
- `picture-side` & `marked-cells`, `picture-side` & `halves`, `picture-side` & `background`, `picture-side` & `stamp-colors`, `picture-side` & `stamp-sites`, `picture-scale` & `marked-cells`, `picture-scale` & `halves`, `picture-scale` & `background`, `picture-scale` & `stamp-colors`, `picture-scale` & `stamp-sites`, `marked-cells` & `halves`, `marked-cells` & `background`, `marked-cells` & `stamp-colors`, `marked-cells` & `stamp-sites`, `halves` & `background`, `halves` & `stamp-colors`, `halves` & `stamp-sites`, `background` & `stamp-colors`, `background` & `stamp-sites`, `stamp-colors` & `stamp-sites`: the two branches' changes applied together
- `picture-side` & `picture-scale`: the half-side test of `$PictureByBlocks` reads blocks at the side that the `picture-scale` branch gives
    - `$PictureByBlocks` & `$ScaleFromBlocks`: the picture is the half whose largest block side exceeds 1, read at that side. The model is undefined where both halves or neither half has such a side.
    - `$PictureByBlocks` & `$StoredPictureExtent`: the picture is the half in blocks of side `half_extent` / 3
    - `$PictureByColors` & `$ScaleFromBlocks`, `$PictureByColors` & `$StoredPictureExtent`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored output extent (18×18): every variant task gives it as the mask extent times the picture extent, so it is derived data and not a second parameter.
- The picture at full resolution, stamped in 6×6 tiles: this is the value 1 of `pattern_scale`, and the pairs rule it out (a 36×36 output).
- `background` by the other color proposers: SharedColor on one input gives each color present, and RarestColor gives 3, 6 and 1 on train0. Neither gives 0 alone, so neither fits.
- A derived `mask_color` or `separator_color` under the concept: the concept's rules read neither value, so no case reads them. Under `$MarkByColor` and `$SplitAtSeparator`, the values are stored, and the derivation of the separator is `$SeparatorAnyLine`.

## Tickets filed
- none
