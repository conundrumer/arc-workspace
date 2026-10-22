# d56f2372

## Concept
- The concept case fits every pair: in each input exactly one color class is unchanged under the mirror about the vertical axis of its bounding box, and its crop on `0` is the output.
- Its rule has a relational form, and no witness has the verdict `other`.

## Choice points
- `selection`
    - `concept`: the kept shape is the one shape that the stored reflection `symmetry` keeps.
    - `$AnySym`: replaces `one-symmetric-shape` and `crop-symmetric-shape`; keeps the one shape that some non-identity D4 element of its bounding box keeps; reads no `symmetry`; undefined on an input where the number of such shapes is not one. Fits every pair.
        - witness `tb-only-symmetric`: breaks `one-symmetric-shape`; plausibility `variant`; verdict `$AnySym`; breaks the invariant that every input holds a shape symmetric about its vertical axis.
    - `$OddSym`: replaces `one-symmetric-shape` and `crop-symmetric-shape`; keeps the one shape whose set of D4 symmetries no other shape of the input has; reads no `symmetry`; undefined on an input where the number of such shapes is not one. Fits every pair.
        - witness `tb-only-symmetric`: breaks `one-symmetric-shape`; plausibility `variant`; verdict `$OddSym`, the grid `$AnySym` gives there; breaks the invariant that every input holds a shape symmetric about its vertical axis.
        - witness `two-shapes` separates it from `$AnySym`: plausibility `variant`; verdict `concept`; breaks the invariant that every input holds at least four shapes.
- `shape-parse`
    - `concept`: a shape is all the cells of one color.
    - `$Components8`: replaces `shapes-on-background`; a shape is one 8-connected piece of one color; undefined on an input where the number of pieces kept is not one. Fits every pair.
        - witness `shared-color-piece`: breaks `one-symmetric-shape`; plausibility `variant`; verdict `$Components8`; breaks the invariant that each color forms one 8-connected piece.
    - `$Components4`: replaces `shapes-on-background`; a shape is one 4-connected piece of one color. Fails Fit at train0: the 8 shape splits into pieces such as the lone cells at (2,3) and (2,5), and several pieces are symmetric, so it is undefined there.
- `output-content`
    - `concept`: the output draws the kept shape's cells in its color on `background` within its bounding box.
    - `$GridWindow`: replaces `crop-symmetric-shape`; the output is the input's window at the kept shape's bounding box, other shapes' cells included. Fits every pair.
        - witness `intruding-cell`: breaks no scene claim; plausibility `borderline`; verdict `concept`; breaks the invariant that no shape has a cell inside another shape's bounding box.
- `background`
    - `concept`: `background` stored as `0`.
    - `background=DominantColor`: replaces the stored `background` with the commonest color of the input; undefined on an input where two colors tie for commonest. Fits every pair.
        - witness `background=DominantColor`: breaks no scene claim; plausibility `borderline`; verdict `concept`; breaks the invariant that the field is the commonest color of each input.
    - `background=SharedColor`: replaces the stored `background` with each color present in the input. Fails Fit at train0: it gives every color of the input, and at a shape's color as the background the field of `0` is a shape and no single shape is kept, so the model is undefined there.
- `selection` & `shape-parse`, `selection` & `output-content`, `selection` & `background`, `shape-parse` & `output-content`, `shape-parse` & `background`, `output-content` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Selection of the kept shape by a rank of size or position: no rank holds over the pairs; in train0 the kept 8 shape ties the 2 shape at 10 cells, and the kept shapes lie at the top in train0 and train2 and at the bottom in train1.
- Symmetry about an axis of the grid in place of the shape's own box: no kept shape lies on a grid axis, so it fails every pair.
- `background` from `RarestColor`, `OutNewColor`, `VanishedColor` and the other color proposers: each gives a shape's color or no color in each input, never the field.
- `symmetry` derived from the evidence: no proposer in `programs/proposers.dl` gives a reflection, and the per-input derivation of a symmetry is the `selection` branches.

## Tickets filed
- none
