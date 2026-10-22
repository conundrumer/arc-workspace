# c658a4bd

## Concept
- Fits every pair (train0, train1, test0).
- The generator draws one nest of concentric 1-wide square rings, one color per ring, with sides n, n-2, … down to 1 or 2. It then scatters each ring in the input as a separate outline, so the output is the nest the outlines came from. On every scene with `size_step` 2, the concept's rank rule (`concentric-rings`) gives that nest. Off that step, the generator's rule is not fixed by the pairs, and the `nesting` branches part there.
- The concept is undefined where the squares are fewer than the output's rings, as on `size-step-four`.
- No witness has the verdict `other`.

## Choice points
- `nesting`: how the ordered squares make the output
    - `concept`: the square of the k-th largest side takes the ring at depth k, in a frame of the largest side; undefined where a ring has no square
    - `$OutlineAtSide`: replaces `concentric-rings`; each square is drawn as a 1-wide outline at its own side, centered in the frame of the largest side, and background fills the rest; undefined where a square's side and the frame's side differ in parity. Fits every pair. Witness `size-step-four`: breaks `sizes-step` (at `size_step` 2), plausibility `variant`, verdict `$OutlineAtSide`, breaks the invariant that the sides fall by 2.
    - `$SolidAtSide`: replaces `concentric-rings`; each square is drawn solid at its own side, centered, the larger ones first; undefined where a square's side and the frame's side differ in parity. Fits every pair. Witness `size-step-four`: breaks `sizes-step`, plausibility `variant`, verdict `$OutlineAtSide`, breaks the invariant that the sides fall by 2.
    - `$SideFromCount`: replaces `output-size`; the frame's side is 2(n-1) plus the smallest square's side, for n squares. Fits every pair. Witness `size-step-four`: breaks `sizes-step`, plausibility `variant`, verdict `$OutlineAtSide`, breaks the invariant that the sides fall by 2.
    - `$InnermostFills`: replaces `concentric-rings`; the smallest square's color fills each ring deeper than the squares reach. Fits every pair. Witness `size-step-four`: breaks `sizes-step`, plausibility `variant`, verdict `$OutlineAtSide`, breaks the invariant that the sides fall by 2.
- `rank-key`: what orders the squares and picks the largest
    - `concept`: the side
    - `$RankByBboxArea`: replaces the order in `concentric-rings` and `output-size`; the squares are ordered by the area of their visible bounding box, and the frame is the side of the top square; undefined where two areas tie. Fits every pair. Witness `cut-to-three-rows`: breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$RankByCellCount`: the squares are ordered by their visible cell count; undefined where two counts tie. Fails Fit at train1 (the 8 square, 22 cells, ranks above the 3 square, 21 cells).
- `side-measure`: how a square's side is read from its visible cells
    - `concept`: the larger extent of its bounding box
    - `$SideOnAxis`: replaces the side read in `concentric-rings` and `output-size`; the bounding box's extent along a stored axis, `axis` = H. Fits every pair. Witness `cut-at-side-edge`: breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$BboxPerAxis`: replaces `output-size`; each square keeps its bounding box's extent on each axis, and the frame is the largest one's bounding box. Fails Fit at train1 (the 3 square shows 7 rows and 9 columns, so the frame is 7×9).
- `square-unit`: what makes one square
    - `concept`: all cells of one color
    - `$Components`: replaces `square-per-color`; each 4-connected component is a square. Fails Fit at train0 (a square of another color cuts the 8 square into two components).
- `bg`: the background color
    - `concept`: stored, `bg` = 0
    - `bg=DominantColor`: the input's most common color. Fits every pair. Witness `bg=DominantColor`: breaks no scene claim, plausibility `borderline`, verdict `concept`, breaks the invariant that background is the most common color by far.
    - `bg=SharedColor`, `bg=VanishedColor`: on one input, each gives every color of that input. Fails Fit at train0 (every value but 0 leaves the model undefined).
    - `bg=RarestColor`: fails Fit at train0 (it gives 4).
- `nesting` & `rank-key`, `nesting` & `side-measure`, `nesting` & `square-unit`, `nesting` & `bg`, `rank-key` & `side-measure`, `rank-key` & `square-unit`, `rank-key` & `bg`, `side-measure` & `square-unit`, `side-measure` & `bg`, `square-unit` & `bg`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- the largest square at the center, the smallest outside: a ring cannot hold a square larger than itself. No pair, variant task or solver header gives this reading.
- the drawing order of the overlapping squares (`occlude`): no output cell depends on which square lies on top. So no reading of the order gives a different output.
- the output side from the input grid's size: the input sides 13, 16 and 19 give the output sides 8, 9 and 10. No rule of the size fits all three.
- `size_step` as a parameter that the program reads: no reading of the rings reads it. The branches that read a square's own side (`$OutlineAtSide`, `$SolidAtSide`) take the step from the sides.

## Tickets filed
- none
