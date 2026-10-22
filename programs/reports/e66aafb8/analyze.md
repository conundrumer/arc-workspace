# e66aafb8

## Concept
- Fits every pair. Each input is invariant under every element of D4 about the grid center, off the mask. The mask is one solid rectangle of 0, and 0 occurs nowhere else. Every element whose image of the mask is clear of the mask gives the expected output.
- Every claim has a relational form, and the concept file's rules are the rules the generator applies. No witness has the verdict `other`.
- `probe.py` runs every branch over the pairs and over the witness inputs.

## Choice points
- `mask-color-source`
    - `concept`: the stored `mask_color`
    - `mask_color=RarestColor`: replaces `one-mask`; `mask_color` is the rarest color of the input. Undefined where that color's cells have no unmasked image. Fails Fit at train0, where the rarest color is 1 (24 cells) and 0 has 40 cells.
    - `mask_color=DominantColor`: replaces `one-mask`; `mask_color` is the commonest color of the input. Its cells spread over the whole grid, so the crop is not the 8×5 frame of the output. Fails Fit at train0.
    - `mask_color=SharedColor`: replaces `one-mask`; on one input, `mask_color` takes every color the input holds, so every cell is masked. Fails Fit at train0.
    - `$AsymmetricMask`: replaces `one-mask`; the mask color is the one color that every pair of cells holding different colors, where an element of `symmetry` maps one onto the other, shares. Undefined where no single color is shared. Fits every pair.
        - witness `other-mask-color`: the test input with colors 0 and 7 swapped, so the mask is 7 and 0 draws part of the pattern. Stands at the stored assignment. Breaks `one-mask` (`mask_color` 0). Plausibility `variant`: a color permutation of this task is a variant task. Invariant broken: the mask is color 0 in every input. Verdict `$AsymmetricMask`.
- `mask-extent`
    - `concept`: every cell of `mask_color` is masked
    - `$MaskComponent`: replaces `one-mask`; the masked cells are the largest connected component of `mask_color`, and other cells of that color are pattern cells. Undefined where two components tie for the largest. Fits every pair.
        - witness `mask-in-pattern`: the test input with the D4 orbit of (2,5) recolored to 0. Stands at the stored assignment. Breaks `one-mask`. Plausibility `borderline`. Invariant broken: the mask color occurs only in the mask. Verdict `$MaskComponent`.
- `symmetry-source`
    - `concept`: the stored `symmetry`
    - `$DerivedSym`: replaces `symmetric-pattern`; derived per input, the elements of D4 about the grid center under which no two unmasked cells disagree. Undefined where those elements leave a masked cell with no unmasked image. Fits every pair.
        - witness `box-only`: the restored test pattern, made mirror-symmetric on both axes and not on the diagonals. One masked cell, (10,15), has mirror images of one color and diagonal images of another. Stands at the stored assignment, where the concept is undefined. Breaks `symmetric-pattern`. Plausibility `variant`: a variant task whose `symmetry` is SYM_BOX routinely gives such an input. Invariant broken: every input is invariant under all of D4 off the mask. Verdict `$DerivedSym`.
- `center`
    - `concept`: the grid's center
    - `$StoredCenter`: replaces the grid center in `symmetric-pattern`; the center is a stored parameter, (23, 23) in doubled coordinates. Fits every pair.
        - witness `other-size`: a 22×22 pattern, symmetric under D4 about its own center. Stands at the stored assignment. Breaks no scene claim. Plausibility `variant`: sibling tasks of this generator use other grid sizes. Invariant broken: every input is 24×24. Verdict `concept`.
    - `$DerivedCenter`: replaces the grid center in `symmetric-pattern`; derived per input, the centers about which no two unmasked cells disagree under any element of `symmetry`, with the most agreeing pairs. The output holds the restoration of each such center. Undefined where a center leaves a masked cell with no unmasked image. Fits every pair.
        - witness `offset-center`: a pattern symmetric under D4 about (12,12), off the grid center. Stands at the stored assignment, where the concept is undefined. Breaks `symmetric-pattern`. Plausibility `variant`: sibling tasks place the symmetry center off the grid center. Invariant broken: every input is symmetric about the grid center. Verdict `$DerivedCenter`.
- `image-combine`
    - `concept`: a masked cell takes the color that its unmasked images share, and the model is undefined where they disagree
    - `$ModalImage`: replaces `restore-by-symmetry`; a masked cell takes the commonest color among its unmasked images. Undefined on a tie. Fits every pair.
        - witness `box-only` (see `$DerivedSym`): `$ModalImage` gives the diagonal color, 9, at (10,15), because four diagonal images outnumber three mirror images. Verdict `$DerivedSym`.
    - `$AnyImage`: replaces `restore-by-symmetry`; the output holds one copy of the patch for each element of `symmetry` whose image of the whole mask is clear of the mask. Undefined where no element is clear. Fits every pair.
        - witness `box-only`: `$AnyImage` gives two grids, the mirror copy and the diagonal copy. Verdict `$DerivedSym`.
- `output-frame`
    - `concept`: the masked rectangle, cropped from the restored pattern
    - `$WholeGrid`: replaces `crop-to-mask`; the output is the whole restored pattern. Fails Fit at train0, whose output is 8×5.
- `mask-color-source` & `mask-extent`, `mask-color-source` & `output-frame`, `mask-extent` & `symmetry-source`, `mask-extent` & `center`, `mask-extent` & `image-combine`, `mask-extent` & `output-frame`, `symmetry-source` & `image-combine`, `symmetry-source` & `output-frame`, `center` & `output-frame`, `image-combine` & `output-frame`: the two branches' changes applied together
- `mask-color-source` & `symmetry-source`: the two branches' changes applied together
    - `$AsymmetricMask` & `$DerivedSym`: each color c, together with the elements of D4 under which the cells not of c agree, where those elements break each cell of c and give it an unmasked image. The mask color and the group are derived together.
- `mask-color-source` & `center`: the two branches' changes applied together
    - `$AsymmetricMask` & `$DerivedCenter`: each color c, together with the centers about which the cells not of c agree under every element of `symmetry`, with the most agreeing pairs. The mask color and the center are derived together.
- `mask-color-source` & `image-combine`: the two branches' changes applied together
    - `$AsymmetricMask` & `$ModalImage`, `$AsymmetricMask` & `$AnyImage`: the model of `$AsymmetricMask` alone. Two unmasked images of one masked cell that disagree are a pair under an element of D4 that holds no mask color, and `$AsymmetricMask` is undefined there.
- `symmetry-source` & `center`: the two branches' changes applied together
    - `$DerivedSym` & `$DerivedCenter`: the pairs of a center and an element of D4 under which no two unmasked cells disagree. The center and the group are derived together.
- `center` & `image-combine`: the two branches' changes applied together
    - `$DerivedCenter` & `$ModalImage`, `$DerivedCenter` & `$AnyImage`: the model of `$DerivedCenter` alone. About a derived center, no two unmasked images of a masked cell disagree.

## Open parameters
- none

## Not formed
- A stored `symmetry` smaller than D4, such as SYM_BOX, SYM_HT or SYM_TB: these are values of `symmetry` with the program unchanged. The determination keeps the largest subgroup that every input keeps off the mask, and that subgroup is D4.
- A mask frame other than the mask's bounding box: the mask is a solid rectangle in every input. No reading of the pairs gives the output another frame.

## Tickets filed
- none
