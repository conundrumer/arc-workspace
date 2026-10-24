# f21745ec

## Concept
- Fits every pair (train0, train1, train2, test0) at `bg` 0, checked by `work/task/f21745ec/check_concept.py` and `work/task/f21745ec/probe.py`.
- No witness has verdict `other`. Every rule has a relational form: equal height and width, a copy at the same place in the box, and erasing are all relational. So the concept file approximates no rule, and the generator's rule is the concept file's rule as written.
- Train2 shows the size match is exact on each axis, with no turn. Its 7 outline is 7×6 and the pattern is 6×7, and the output erases it.

## Choice points
- `outline-match`: which empty outlines receive the pattern
    - `concept`: the outlines whose height and width both equal the patterned rectangle's
    - `$SizeUpToTurn`: replaces `same-size-gets-pattern`. An outline whose height and width are the pattern's swapped also gets the pattern, turned a quarter turn. No parameters. Defined wherever the concept is. Fails Fit at train2: the 7×6 outline of 7 would get the turned 6×7 pattern, but the output erases it.
    - `$SizeByArea`: replaces `same-size-gets-pattern`. An outline whose area equals the pattern's gets the pattern. No parameters. Undefined where an outline has equal area and other dimensions. Fails Fit at train2: the 7×6 outline of 7 has area 42, like the 6×7 pattern, so the branch is undefined there.
    - `$SizeOnOneAxis`: replaces `same-size-gets-pattern` and `other-size-erased`. An outline matches when its extent on the stored axis equals the pattern's. Parameter `match_axis`: `AXIS_V`, since `AXIS_H` fails train1, where the 4×5 outline of 7 has the pattern's width 5 and is erased. Undefined where an outline matches on that axis and differs on the other, since the pattern does not fit. Fits every pair. Witness `same-height-other-width`: breaks no scene claim, stands at the stored assignment, plausibility `ordinary`, verdict `concept`. On it the branch is undefined and the concept erases the outline. No witness exists where the branch is defined and differs: wherever it is defined it gives the concept's output, so the concept subsumes it and it fails Subsumption.
- `unmatched-outline`: what becomes of an empty outline whose size differs
    - `concept`: it is erased to `bg` (`other-size-erased`)
    - `$KeepUnmatched`: replaces `other-size-erased`. The outline stays as it is. No parameters. Defined wherever the concept is. Fails Fit at train0: the 5×5 outline of 5 stays, but the output erases it.
- `pattern-source`: which rectangle supplies the pattern
    - `concept`: the one rectangle with cells of its color inside its border (`one-patterned-rectangle`)
    - `$SourceMostCells`: replaces `one-patterned-rectangle` in the rules' reading. The source is the rectangle with the most cells. No parameters. Undefined where two rectangles tie for the most cells. Fits every pair: the patterned rectangle has the most cells in each, 33 against 28 in test0. Witness `most-cells-source`: breaks no scene claim, stands at the stored assignment, plausibility `ordinary`, verdict `concept`.
    - `$SourceLargestBox`: replaces `one-patterned-rectangle` in the rules' reading. The source is the rectangle with the largest box. No parameters. Undefined where boxes tie. Fails Fit at train0: the 8, 6 and 4 rectangles are all 7×8, so it is undefined.
    - `$SourceColorStored`: replaces `one-patterned-rectangle` in the rules' reading. The source is the rectangle of a stored color `source_color`. Undefined where no rectangle has that color. Fails Fit at train1: train0 needs 8, and train1 has no 8. No one value fits every pair (8, 5, 8).
- `copy-color`: the color the copied pattern takes
    - `concept`: the receiving outline's own color
    - `$PatternColorKept`: replaces `same-size-gets-pattern`. The copy keeps the pattern's color. No parameters. Defined wherever the concept is. Fails Fit at train0: the 6 and 4 outlines would get 8.
- `copy-orientation`: the transform the copy applies to the pattern
    - `concept`: none. The cell at the same place in the box is copied.
    - `$CopyTransformed`: replaces `same-size-gets-pattern`. The copy applies a stored D4 element `copy_d4`, and an outline matches when its dimensions equal the transformed pattern's. The pairs determine `D4_ID`: each other element moves train0's asymmetric 8 pattern. Defined wherever the concept is. Fits every pair. Witness `copy-reflected`: breaks no scene claim, stands at the assignment `copy_d4` = `D4_LR` (at `D4_ID` it agrees with the concept everywhere), plausibility `ordinary`, verdict `concept`.
- `pattern-rectangle`: what becomes of the patterned rectangle
    - `concept`: it stays (`pattern-kept`)
    - `$PatternErased`: replaces `pattern-kept`. The patterned rectangle is erased to `bg`. No parameters. Defined wherever the concept is. Fails Fit at train0: the output keeps the 8 rectangle.
- `bg`: where the background color comes from
    - `concept`: stored, `bg` 0
    - `bg=DominantColor`: derives `bg` on each input as its commonest color, replacing the stored `bg` of `rectangles-on-background`. Undefined where two colors tie for commonest. Fits every pair, since 0 is the commonest color of each input. Witness `bg=DominantColor`: breaks the scene claim `rectangles-on-background` (the field is 8, not 0), stands at the stored assignment, plausibility `variant`, verdict `bg=DominantColor`. The invariant of the inputs it breaks: every input's field is 0. A color-permuted variant task has this field, and a person reads 8 as the background there.
- `outline-match` & `unmatched-outline`, `outline-match` & `pattern-source`, `outline-match` & `copy-color`, `outline-match` & `copy-orientation`, `outline-match` & `pattern-rectangle`, `outline-match` & `bg`, `unmatched-outline` & `pattern-source`, `unmatched-outline` & `copy-color`, `unmatched-outline` & `copy-orientation`, `unmatched-outline` & `pattern-rectangle`, `unmatched-outline` & `bg`, `pattern-source` & `copy-color`, `pattern-source` & `copy-orientation`, `pattern-source` & `pattern-rectangle`, `pattern-source` & `bg`, `copy-color` & `copy-orientation`, `copy-color` & `pattern-rectangle`, `copy-color` & `bg`, `copy-orientation` & `pattern-rectangle`, `copy-orientation` & `bg`, `pattern-rectangle` & `bg`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Copying only the interior of the patterned rectangle instead of its whole box: two boxes of one size have the same border, so the two copies agree on every input. The model is equivalent to the concept's.
- Finding rectangles as connected components instead of by color: this is a parse, not a claim. Under `rectangles-on-background` each rectangle has its own color, so grouping by color and by the box of the outline agree wherever that claim holds. A component parse also splits off train0's pattern cells at (4,5), (4,6), (5,4), (5,5), which touch no border cell.

## Tickets filed
- none
