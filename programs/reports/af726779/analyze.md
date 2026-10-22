# af726779

## Concept
- The concept case fits every train and test pair (`check_concept.py`).
- No witness has the verdict `other`.
- The generator applies the rule as the concept file states it: a mark goes `level-step` lines past each single-cell gap between two marks of a level, and the levels take turns between the base color and the new color.

## Choice points
- `growth-dir`
    - `concept`: stored, down
    - `$GrowFarSide`: replaces `growth-dir` stored with a value derived from the input, toward the side of the base line with more lines; undefined where the two sides have the same number of lines. Fails Fit at train2, where the base line has 4 rows on each side.
    - `$GrowBothSides`: replaces `gap-mark` and `stop` so that the levels grow toward both sides of the base line. Fails Fit at train1, where it marks row 0.
- `gap-test`
    - `concept`: a cell becomes a mark when both cells beside it on the level are marks and the cell itself is not
    - `$BetweenTwoMarks`: replaces `gap-mark` with a version that leaves out the test that the cell itself is not a mark. Fails Fit at train1, where the base run `7 7 7` at cols 0–2 marks (4,1).
    - `$GapCenter`: replaces `gap-mark` with a version that puts the mark at the center of each gap of odd width between two marks. Fails Fit at train2, where the width-3 gap between (6,4) and (6,8) marks (8,6).
    - `$EdgeAsMark`: replaces `gap-mark` with a version that counts a cell off the grid as a mark. Fails Fit at train0, where it marks (5,0).
- `level-color`
    - `concept`: stored parity map, 7 at even levels and 6 at odd levels
    - `$EvenColorOfBase`: replaces `level-color` with a version where the program derives the even-level color as the color of the base line's marks, and the odd levels take the stored 6. Fits every pair. Witness `base-color-2`: breaks scene claim `base-line` (`mark-color` 7). It stands at the stored assignment. Plausibility `variant` (every input's marks are 7). Verdict `$EvenColorOfBase`.
    - `$ColorBySuccession`: replaces `level-color` with a stored successor map {7→6, 6→7}, where each level's color follows the color of the level before it. Where the map has no successor, the model adds no further level. Fits every pair. Witness `base-color-2`: breaks scene claim `base-line` (`mark-color` 7). It stands at the stored assignment. Plausibility `variant` (every input's marks are 7). Verdict `$EvenColorOfBase`.
- `background`
    - `concept`: stored, 3
    - `background=DominantColor`: replaces `background` stored with the color that has the most cells in the input. Fits every pair. Witness `background=DominantColor`: breaks scene claim `background` (3). It stands at the stored assignment. Plausibility `variant` (every input's background is 3). Verdict `background=DominantColor`.
- `growth-dir` & `gap-test`, `growth-dir` & `level-color`, `growth-dir` & `background`, `gap-test` & `level-color`, `gap-test` & `background`, `level-color` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Derivation of the odd-level color 6 by OutNewColor or AnyOutNewColor: on an input alone, `ex_out` is empty and these derivations give no value. 6 is in no input, so no derivation from the input gives it.
- Derivation of the even-level color by RarestColor: `level-colors` is keyed by parity, and the proposer gives one color. The derivation of that color from the input is formed as `$EvenColorOfBase`.
- Derivation of `background` by SharedColor: on one input it gives 3 and 7 together. A base line that is all background has no marks, so the model adds nothing and fails Fit at train0.
- Derivation of `background` by the proposers that read `ex_out` (UnchangedColor and the others): on an input alone they give no value.
- A triangle drawn over each maximal run of alternating marks: the triangles of two runs are 3 or more cells apart at level 1 and do not meet after that, so this reading marks the same cells as `gap-mark`.
- Marks from different levels pooled when they lie on one line: under `base-line` each line holds the marks of one level only. A reading that pools them differs from the concept only on inputs with a second marked line, and no pair shows how such a line's new marks are colored.
- A derived `level-step`: no feature of the input gives the number 2, and no proposer gives a line spacing.

## Tickets filed
- none
