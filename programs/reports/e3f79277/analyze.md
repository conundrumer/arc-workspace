# e3f79277

## Concept
- The concept case fits every pair: train0, train1 and test0 each give the triangle outline with legs of 2k in the angle's corner, on a 16x16 field of 7.
- No witness has verdict `other`.
- The concept case is undefined where the input field is not 7, where the two legs differ in length, and where no corner holds the angle.

## Choice points
- `background`
    - `concept`: the background color is stored as 7
    - `background=DominantColor`: replaces `corner-angle`, `no-other-marks` and `canvas` in where the background color comes from: it is the input's commonest color; undefined on no input that has a single commonest color. It fits every pair.
        - witness `background=DominantColor`: a 6x6 field of 3 with a 5 angle of legs 2 in the top-left corner; at the stored assignment; breaks `corner-angle`, whose field is the `background` color 7; plausibility `variant`; verdict `background=DominantColor`; it breaks the invariant that every input field is 7.
- `out_size`
    - `concept`: the output side is stored as 16
    - `$SizeFromInput`: replaces `canvas`: the output side is the input side plus a stored `size_gap` of 10; undefined on no input. It fits every pair.
        - witness `size-from-input`: an 8x8 field of 7 with a 5 angle of legs 2 in the top-left corner; at the stored assignment; breaks `corner-angle`, whose input side is `in_size` 6; plausibility `variant`; verdict `concept`; it breaks the invariant that every input is 6x6.
- `leg-length`
    - `concept`: both legs share one length k, and the output legs are `leg_scale` times k; undefined where the legs differ
    - `$LongerLeg`: replaces `corner-angle` and `scaled-legs`: k is the length of the longer leg, and both output legs take `leg_scale` times it; undefined on no input with an angle in a corner. It fits every pair.
        - witness `unequal-legs`: a 6x6 field of 7 with a 5 angle in the bottom-right corner, row leg 3 and column leg 2; at the stored assignment; breaks `corner-angle`, whose legs are equal; plausibility `foreign`; verdict `any`; it breaks the invariant that the two legs of every input are equal.
    - `$ShorterLeg`: replaces `corner-angle` and `scaled-legs`: k is the length of the shorter leg, and both output legs take `leg_scale` times it; undefined on no input with an angle in a corner. It fits every pair.
        - witness `unequal-legs`, as for `$LongerLeg`.
    - `$LegOffset`: replaces `scaled-legs`: each output leg is k plus a stored offset. It fails Fit at train1: train0 fixes the offset at 2, and train1 needs 3.
    - `$FixedLegLength`: replaces `scaled-legs`: each output leg has a stored length. It fails Fit at train1: train0 fixes the length at 4, and train1 needs 6.
- `angle-color`
    - `concept`: the triangle takes the color of the input angle
    - `$StoredAngleColor`: replaces `scaled-legs` and `hypotenuse` in where the color comes from: a stored color. It fails Fit at train1: train0 fixes the color at 5, and train1 needs 9.
- `corner`
    - `concept`: the triangle sits in the output corner that matches the input angle's corner
    - `$StoredCorner`: replaces `same-corner`: a stored corner. It fails Fit at train1: train0 fixes the bottom-right corner, and train1 needs the bottom-left.
- `hypotenuse`
    - `concept`: the diagonal between the far ends of the legs is drawn
    - `$NoHypotenuse`: drops `hypotenuse`. It fails Fit at train0: train0 output (13,14) and (14,13) are 5 on the diagonal.
- `background` & `out_size`, `background` & `leg-length`, `background` & `angle-color`, `background` & `corner`, `background` & `hypotenuse`, `out_size` & `leg-length`, `out_size` & `angle-color`, `out_size` & `corner`, `out_size` & `hypotenuse`, `leg-length` & `angle-color`, `leg-length` & `corner`, `leg-length` & `hypotenuse`, `angle-color` & `corner`, `angle-color` & `hypotenuse`, `corner` & `hypotenuse`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- the output side as a whole multiple of the input side: 16 is no whole multiple of 6, so `ScaleRatio` proposes nothing.
- the output side derived by `ConstOutDim` or `DimDiff`: each reads `ex_out`, which is empty in a run on one input, so the branch is undefined on every pair and fails Fit.
- the background derived by `SharedColor` or `RarestColor`: `SharedColor` gives both colors of an input and `RarestColor` gives the angle color, so no cell is left as the angle and the branch fails Fit at train0.
- each leg scaled by its own length: with unequal legs the far ends are joined by a line that is not a diagonal, and drawing it needs a slope, a number that counts nothing the task has, so the claim has no relational form.
- an angle off the corner: every input puts the angle's vertex on the corner cell, and no source gives a reading of where the triangle goes when it is not there.

## Tickets filed
- none
