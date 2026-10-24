# f3e14006

## Concept
- Fits train0, train2, train3, test0 and test1 exactly. At train1 the pair's output holds `8` at output (4,3), (4,5), where the concept, and every branch, gives the cross line's base `5`; no interpretation found reproduces those two cells, and `progress-analyze.md` records it. Judged by the concept's output there, the concept fits every pair.
- Every rule has a relational form; the program runs no approximation. No witness with verdict `other`.
- Against the concept: at the `anchor-across-bar-line` witness the verdict is `$AnchorAcrossBarLine`. In every pair the bar line's own row is a hole row, its holes in the bar's mark color; anchoring at the stored top corner matches that only because the three pairs whose bar line lies below the cross marks (train0, train2, test1) have odd heights.
- `anchor_corner` (top-left) is read on each axis only under that axis's concept branch; a case taking both anchor branches reads no `anchor_corner`.

## Choice points
- `anchor-across`: which end of the rectangle, across `bar_axis`, starts with a hole line
    - `concept`: the side of the stored `anchor_corner` (the top)
    - `$AnchorAcrossBarLine`: replaces `lattice` across `bar_axis`: hole lines start at the bar line and alternate away from it; reads no side of `anchor_corner` across; undefined on no input where the concept is defined. Fits every pair. Witness `anchor-across-bar-line` (train0 with the cross marks at rows 2 and 6), at the stored assignment, breaks no scene claim, plausibility `ordinary`, verdict `$AnchorAcrossBarLine`.
- `anchor-along`: which end of the rectangle, along `bar_axis`, starts with a hole line
    - `concept`: the side of the stored `anchor_corner` (the left)
    - `$AnchorAlongNearCross`: replaces `lattice` along `bar_axis`: hole lines start at the bar mark nearer the cross line (where the two are equally near, the width is odd and both ends give one lattice); reads no side of `anchor_corner` along; undefined on no input where the concept is defined. Fits every pair. Witness `anchor-along-near-cross` (train3 with the cross line moved to col 7), at the stored assignment, breaks no scene claim, plausibility `ordinary`, verdict `concept`.
- `background`: where the background color comes from
    - `concept`: stored `background` = 0
    - `background=DominantColor`: `background` derived as the commonest color of the input; undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor` (train1 with the field recolored to 1), at the stored assignment, breaks the scene claim `two-crossing-lines` (a field of `background` = 0), plausibility `variant`, verdict `background=DominantColor`; it breaks the invariant of the inputs that every field is color 0.
- `anchor-across` & `anchor-along`, `anchor-across` & `background`, `anchor-along` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored choice of which line lies on top at thread crossings: no value fits, since train0 shows the bar line on top and train2 the cross line; the concept reads it from the input's crossing cell.
- `bar_axis` derived from the input: no input feature tells the bar line from the cross line (train0's grid is square; in train0 the marks of each line lie on one side of the other line; in train1 both mark pairs are 4 apart), and no proposer derives an axis.
- Hole lines across `bar_axis` starting at the farther cross mark: fails Fit at train3 (it makes rows 11, 9, 7, 5 the hole rows).
- Hole lines along `bar_axis` starting at the bar mark farther from the cross line: fails Fit at train3 (cols 8, 6, 4).
- Lattice parity at fixed grid coordinates, or at the cross line's column: fails Fit at train3 (holes at the odd cols 3, 5, 7) and at train1 (cross line at col 7, holes at cols 2, 4, 6).
- Rectangle extent across `bar_axis` from the cross marks alone: fails Fit at train0 (rows 1–6 in place of 1–9). Extent along `bar_axis` reaching the cross line: fails Fit at train0 (cols 2–8 in place of 6–8).
- Hole color by the nearer of the bar line and the cross marks: fails Fit at train0 (row 7 would take the cross mark color 2; the output has 5).
- Hole color by lying beyond the nearer cross mark in place of within the marks' span: the two readings agree wherever the cross marks lie on one side of the bar line, and where the marks straddle it the concept's `rectangle` rule has no reading of "the farther mark", so no separate model is formed.
- `background` derived by SharedColor: on one input it gives every color of that input, so each case taking it gives several grids at a train pair and fails Fit. By RarestColor: gives a mark color, fails Fit at train0. The proposers that read outputs (UnchangedColor, ChangedColor, VanishedColor and the rest) read no output under a `@derive` branch.

## Tickets filed
- none
