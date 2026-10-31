# f0afb749

## Concept
- Fits every pair: train0–2 and test0 (`work/task/f0afb749/check_concept.py`). All rules have a relational form. The rule is exact: it is how the generator works (scale by 2, then draw the main diagonal through each block over the background), so it approximates nothing.
- Every input holds the scene claims `single-cell-marks`, `one-mark-color`, `square-grid` and `one-mark-per-diagonal`.
- `one-mark-per-diagonal` is the only condition under which a line never meets a block other than its own. A line on output diagonal 2d crosses only the blocks of marks on input diagonal d.
- No witness has verdict `other`.

## Choice points
- `line-at-other-block`: what a mark's line does where it meets another mark's block
    - `concept`: the line paints background cells only. It passes behind other blocks and carries on beyond them (`diagonal-through-block`).
    - `$LineOverBlocks`: replaces `diagonal-through-block`. Each mark's line takes `line_color` on every cell of its diagonal outside the mark's own block, so it paints over other marks' blocks. Same parameters, defined on every input.
        - Standing: fits every pair.
        - Witness `shared-diagonal`: the input below, at the stored assignment. It breaks `one-mark-per-diagonal`, the invariant that no two marks share a main diagonal.
            ```
            5 0 0
            0 0 0
            0 0 5
            ```
        - Plausibility `variant`, verdict `concept`.
    - `$RayStopsAtBlock`: replaces `diagonal-through-block`. From each block's two diagonal corners, a ray goes outward toward the top-left and bottom-right. It paints background cells and stops at the first cell that is not background. Same parameters, defined on every input.
        - Standing: fits every pair, but fails Equivalence with the concept case.
        - Why they are equivalent: the line on output diagonal 2d runs through the scaled cells of input diagonal d. Each stretch of background on that diagonal touches a mark of the diagonal at one end, and that mark's ray covers the stretch. A check over 3000 random grids with any colors found no difference.
        - There is no witness for it.
- `background`: where the background color comes from
    - `concept`: stored, `0`
    - `background=DominantColor`: derived as the commonest color of the input alone. Undefined where two or more colors tie for the commonest, since the background then takes two values.
        - Standing: fits every pair.
        - Witness `background=DominantColor`: a field of 7 with a lone 0 at (1,1), at the stored assignment. It breaks `single-cell-marks`: at background 0, the 7 cells are the marks and they touch. It also breaks the invariant that background 0 fills every input apart from isolated marks.
        - Plausibility `variant` (a color-permuted variant task produces this input), verdict `background=DominantColor`.
    - `background=RarestColor`: derived as the rarest color of the input. It fails Fit at train0, where it gives 5.
    - `background=SharedColor`: derived from one input, it gives every color present. It fails Fit at train0, where the background takes two values and the model is undefined.
- `line_color`: where the line color comes from
    - `concept`: stored, `1`
    - `line_color=OutNewColor`: with `ex_out` empty, it derives no value from an input alone, so the model is undefined everywhere. It fails Fit at train0.
    - `line_color=AnyOutNewColor`: the same, and it fails Fit at train0.
- `scale`: where the scale factor comes from
    - `concept`: stored, `2`
    - `scale=ScaleRatio`: derives no value from an input alone, with `ex_out` empty. It fails Fit at train0.
    - `$ScaleByColorCount`: replaces `scale-up`. The scale is derived as the number of distinct colors of the input, background included, as 469497ad's header derives its scale from a color count. Defined on every nonempty input.
        - Standing: fits every pair, since every input has 2 colors.
        - Witness `two-mark-colors`: marks 5 at (0,1) and 2 at (2,0) in a 3×3 field of 0, at the stored assignment. It breaks `one-mark-color`, the invariant that every input has exactly one mark color.
        - Plausibility `variant`, verdict `concept`.
- `line-at-other-block` & `background`, `line-at-other-block` & `line_color`, `line-at-other-block` & `scale`, `background` & `line_color`, `background` & `scale`, `line_color` & `scale`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Both diagonals through each block (an X): train0 shows no anti-diagonal cells, so it fails Fit at train0. It is not a reading of these pairs.
- A line toward one side only, top-left or bottom-right: train0 shows both sides of the block at rows 2–3, cols 2–3, at (0,0)–(1,1) and (4,4)–(9,9).
- Drawing the diagonal at input resolution and then scaling, which gives 2-wide lines: train0's lines are 1 wide.
- A 2×2 identity stamp on each background input cell on a mark's diagonal: this gives the concept's model under another formulation, not another model.
- A line color taken from the mark: the line is 1 in every pair, while the marks are 5, 2, 3 and 4.
- Deriving `line_axis` from the input: the inputs show no feature that picks the main diagonal over the anti-diagonal. Every input also has one mark per anti-diagonal.

## Tickets filed
- none
