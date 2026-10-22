# db0c5428

## Concept
- The concept fits every train pair and the test pair (probe `work/task/db0c5428/probe.py`).
- Each rule has a relational form, and no witness has the verdict `other`.
- The output frame is the input frame in every pair, and every input square is D4-symmetric, with a margin of at least 3 cells from each grid edge.

## Choice points
- `outer-copy`: what the block place at 2d from the hole receives
    - `concept`: the block at -d from the hole, unturned (`copy-across`)
    - `$MirrorOut`: replaces `copy-across`; the block place at 2d receives the block at d mirrored across the side or the corner it faces (flipped top to bottom for an up or down d, left to right for a left or right d, and both for a corner d); no parameters; undefined on no input where the concept is defined. Fits every pair.
        - witness `asymmetric-edge-block`, which breaks `d4-symmetric`, at the stored assignment; plausibility `borderline`, verdict `concept`; invariant broken: every input square is unchanged under each element of D4
    - `$HalfTurnOut`: replaces `copy-across`; the block place at 2d receives the block at d turned a half turn; no parameters; undefined on no input where the concept is defined. Fits every pair.
        - witness `asymmetric-edge-block`, which breaks `d4-symmetric`, at the stored assignment; plausibility `borderline`, verdict `concept`; invariant broken: every input square is unchanged under each element of D4
- `hole-center`: the color of the hole's center cell
    - `concept`: the color of the frame cells at offsets (±1, ±2) and (±2, ±1) from the hole's center (`fill-hole`)
    - `$CenterCommon`: replaces the center part of `fill-hole`; the center cell takes the commonest color of the square's eight outer blocks; no parameters; undefined where two colors tie for commonest. Fits every pair.
        - witness `rare-frame-color`, which breaks no scene claim; plausibility `ordinary`, verdict `concept`
    - `$CenterCorner`: replaces the center part of `fill-hole`; the center cell takes the color of the square's corner cells; no parameters. Fails Fit at test0, where it gives 3 at (8,8) and the output has 7.
- `background`: the field color
    - `concept`: stored, 8
    - `background=DominantColor`: replaces the stored `background` read by `one-square`, `block-grid` and `rest-background` with the color that has the most cells in the input; undefined where two colors tie for most cells. Fits every pair.
        - witness `background=DominantColor`, which breaks `one-square` (no field of 8), at the stored assignment; plausibility `variant`, verdict `background=DominantColor`; invariant broken: the field is 8 in every input
- `overhang`: what happens to the cells of a copy that fall past the grid edge
    - `concept`: those cells are dropped, and the output frame is the input frame
    - `$GrowFrame`: adds `grow-frame`: the output frame extends past each edge by the number of copy rows or columns that fall past it, and the new cells take the rules' colors; no parameters; undefined on no input where the concept is defined. Fits every pair.
        - witness `edge-overhang`, which breaks `room`, at the stored assignment; plausibility `borderline`, verdict `concept`; invariant broken: the square stands at least 3 cells from each grid edge in every input
- `outer-copy` & `hole-center`, `outer-copy` & `background`, `outer-copy` & `overhang`, `hole-center` & `background`, `hole-center` & `overhang`, `background` & `overhang`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A hole cell at offset d taking the inner-facing cell of the block at d: that cell is the input cell at offset 2d, so the model is the concept's on every input.
- A hole cell at offset d taking the input cell at offset -2d: no pair, solver header or variant task gives a turned frame, and the pairs show the frame copied in its own orientation.
- A field color from `SharedColor` or `RarestColor`: on one input, `SharedColor` gives every color of that input and `RarestColor` gives a pattern color, so neither gives the field.
- A block side other than 3: the hole-center rule reads offsets that exist only for a 3×3 hole, so no other block side gives a model of the same rules.

## Tickets filed
- none
