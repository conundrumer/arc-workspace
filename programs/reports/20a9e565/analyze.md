# 20a9e565

## Concept
- The concept case fits every pair. The task is a nested task: each input holds a sequence whose consecutive terms are its demonstrated pairs, so the concept case reads a catalog of five growth rules, one per input, as [Demonstrated choice](docs/handbook/solver-file.md#demonstrated-choice) gives. The rules are:
    - an E that widens its arms and lengthens its stem
    - a column of L-triominoes that lengthens at both ends
    - a column of a two-row motif that lengthens at one end
    - a band of a periodic zigzag that widens by half a period at each end
    - a stepped tent that gains one step
- The rule as the generator applies it: the sequence goes on by whatever progression its maker drew, as a person reads it from the shown terms. Each input of the task shows a progression of its own, so `continue-sequence` is approximated by the catalog of the five progressions the inputs show.
- Witness `ring-sequence`: a sequence of hollow squares growing by 2 on each axis. No catalog rule is consistent with it, so the concept case is undefined. It breaks no scene claim. Plausibility `ordinary`, verdict `other`: the right part of the next square, in color 3.

## Choice points
- `growth-rule`
    - `concept`: the catalog of the five growth rules, the rule for an input being one that each of its consecutive shown terms confirms
    - `$SliceGrowth`: replaces `continue-sequence` with the slice reading of 2ccd9fef (`slices`, `growth`): each term is read as slices across the sequence's direction, a fixed lead, a repeating block and a fixed tail, and each edge of the term's box moves by a step; no parameters; undefined where a slice changes from one term to the next. Fails Fit on train 0: the stem of each E lengthens from term to term, so no slice is fixed.
- `sequence-direction`
    - `concept`: the direction in which the terms follow one another, read per input from the shown terms
    - `sequence_dir=stored`: stores that direction, toward the right. Fails Fit on test 0, whose terms follow one another upward.
- `term-spacing`
    - `concept`: the next term stands one gap past the last term, with the gap read from the shown terms
    - `term_gap=stored`: stores the gap, 1; defined wherever the concept case is. Fits every pair. Witness `term_gap=stored`: train 2 with gaps of 2 columns. It breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `$ConstantOffset`: replaces the spacing in `continue-sequence`: the offset from the last term to the next repeats the last offset between shown terms. Fails Fit on train 0: the offsets 3, 4, 5 put the next term at cols 18–23, and the output shows it at cols 19–24.
- `term-alignment`
    - `concept`: the line on which the terms align across the sequence's direction, read per input from the shown terms
    - `term_align=stored`: stores that alignment. Fails Fit: no one alignment fits train 0 (bottom), train 1 (center) and train 2 (top).
- `color-cycle`
    - `concept`: the shown term colors repeat with their least period, and a new term takes the color one period back
    - `$DistinctColorCycle`: replaces the cycle in `continue-sequence`: the period is the number of distinct shown colors; undefined where the shown colors do not repeat with that period. Fits every pair. Fails Subsumption: where the shown colors repeat with the distinct count, that count is their least period. Witness `distinct-color-cycle`: train 2 with term colors 7 2 7 3 7, on which the branch is undefined. It breaks no scene claim. Plausibility `variant`, verdict `concept`. Invariant broken: in every input, the colors of one period are distinct.
    - `color_period=stored`: stores the period, 3. Fails Fit on test 0, whose colors 6 4 6 4 have period 2.
- `drawn-terms`
    - `concept`: every term of the continued sequence, the shown terms included
    - `$NewTermsOnly`: adds to `crop-window`: only the terms past the last shown one are drawn. Fits every pair. Witness `new-terms-only`: train 0 with the window at rows 20–23, cols 12–18, over the stem of the last shown term. It breaks `window-ahead`. Plausibility `borderline`, verdict `concept`. Invariant broken: in every input, the window lies past the last shown term.
    - `$NextTermOnly`: adds to `crop-window`: only the term right after the last shown one is drawn. Fails Fit on train 2: the window frames the second term past the last, at cols 25–27, which that term does not reach.
- `window-extent`
    - `concept`: the box of the mark cells
    - `$WindowInterior`: replaces the extent in `crop-window` with the box's interior. Fails Fit on train 0: it gives 1×4, and the output is 3×6.
- `mark-cells`
    - `concept`: the window's mark cells take the sequence's colors
    - `$MarksDrawn`: replaces that part of `crop-window`: the marks stay drawn over the output. Fails Fit on train 0: output (0,0) is 2, and the mark gives 5.
- `window-marks`
    - `concept`: the window is the box of the `marker_color` cells, at whichever two opposite corners the marks stand
    - `$StoredMarkCorners`: makes `marker_corners` a parameter that the rule reads, top-left and bottom-right, and finds the window from a mark at each of those corners; undefined where the marks stand at the other two corners. Fits every pair. Fails Subsumption: where it is defined, it frames the same box. Witness `stored-mark-corners`: train 0 with its marks at the top-right and bottom-left corners of the same window, on which the branch is undefined. It breaks `corner-marks`. Plausibility `variant`, verdict `concept`. Invariant broken: in every input, the marks stand at the top-left and bottom-right corners.
- `marker_color`
    - `concept`: stored, 5
    - `marker_color=RarestColor`: derives `marker_color` as the input's rarest color, ties included; undefined where the cells of that color do not form two L marks. Fits every pair. Witness `marker_color=RarestColor`: train 2 with its marks in color 6. It breaks `corner-marks`. Plausibility `variant`, verdict `marker_color=RarestColor`. Invariant broken: in every input, the marks are 5.
    - `marker_color=VanishedColor`: derives every color of the input, since `ex_out` is empty on one input. Fails Fit on train 0.
    - `marker_color=SharedColor`: derives every color of the input. Fails Fit on train 0.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: derives `background` as the input's commonest color. Fits every pair. Witness `background=DominantColor`: train 2 on a field of 8. It breaks `growing-sequence`. Plausibility `variant`, verdict `background=DominantColor`. Invariant broken: in every input, the background is 0.
    - `background=SharedColor`: derives every color of the input. Fails Fit on train 0.
- `growth-rule` & `sequence-direction`, `growth-rule` & `color-cycle`, `growth-rule` & `drawn-terms`, `growth-rule` & `window-extent`, `growth-rule` & `mark-cells`, `growth-rule` & `window-marks`, `growth-rule` & `marker_color`, `growth-rule` & `background`, `sequence-direction` & `term-spacing`, `sequence-direction` & `term-alignment`, `sequence-direction` & `color-cycle`, `sequence-direction` & `drawn-terms`, `sequence-direction` & `window-extent`, `sequence-direction` & `mark-cells`, `sequence-direction` & `window-marks`, `sequence-direction` & `marker_color`, `sequence-direction` & `background`, `term-spacing` & `term-alignment`, `term-spacing` & `color-cycle`, `term-spacing` & `drawn-terms`, `term-spacing` & `window-extent`, `term-spacing` & `mark-cells`, `term-spacing` & `window-marks`, `term-spacing` & `marker_color`, `term-spacing` & `background`, `term-alignment` & `color-cycle`, `term-alignment` & `drawn-terms`, `term-alignment` & `window-extent`, `term-alignment` & `mark-cells`, `term-alignment` & `window-marks`, `term-alignment` & `marker_color`, `term-alignment` & `background`, `color-cycle` & `drawn-terms`, `color-cycle` & `window-extent`, `color-cycle` & `mark-cells`, `color-cycle` & `window-marks`, `color-cycle` & `marker_color`, `color-cycle` & `background`, `drawn-terms` & `window-extent`, `drawn-terms` & `mark-cells`, `drawn-terms` & `window-marks`, `drawn-terms` & `marker_color`, `drawn-terms` & `background`, `window-extent` & `window-marks`, `window-extent` & `marker_color`, `window-extent` & `background`, `mark-cells` & `window-marks`, `mark-cells` & `marker_color`, `mark-cells` & `background`, `window-marks` & `marker_color`, `window-marks` & `background`, `marker_color` & `background`: the two branches' changes applied together
- `growth-rule` & `term-spacing`: the `$SliceGrowth` model alone. Its box edges place each term, so the gap and the offset do not exist with it, and `term-spacing` stands under the concept branch of `growth-rule`.
- `growth-rule` & `term-alignment`: the `$SliceGrowth` model alone. Its box edges place each term, so the alignment does not exist with it, and `term-alignment` stands under the concept branch of `growth-rule`.
- `window-extent` & `mark-cells`: the `$WindowInterior` model alone. The box's interior holds no mark cell, so `mark-cells` stands under the concept branch of `window-extent`.

## Open parameters
- none

## Not formed
- The window as a crop of the input with the continuation drawn over it and the marks removed: the continued sequence holds the shown terms, and the marks are the only other cells, so this model is equivalent to the concept case.
- In test 1, the colors of a tent block alternate from a bottom step of 3, against each block's top color alternating from block to block: each block gains one step, so the two readings color every block alike, and their models are equivalent.
- The window as the box that the corner cells of the two L marks bound: that box is the box of the mark cells.

## Tickets filed
- 4-60_task_20a9e565_analyze.md
