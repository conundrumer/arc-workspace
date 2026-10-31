# f35d900a

## Concept
- Fits every pair: train0–3 and test0 (`work/task/f35d900a/check_concept.py`, `work/task/f35d900a/probe.py`). Each marker gets a 3×3 ring of the other marker color. On each side of the rectangle, the cells between the two rings take `dot_color` where their distance to the nearer ring is odd.
- No witness has verdict `other`. No rule is an approximation: `dotted-sides` compares two distances and reads their parity, which is relational.
- The pairs fix that dots run from both ends (train0 row 2 cols 3–4 are both dotted) and that each end stops at the middle (train1 col 2 rows 5–12 dots only 5, 7, 10, 12). They do not fix how far an end reaches once a gap holds more than 8 cells, or whether an end's dots are cut at the middle on a gap of 4 or 6. Every gap in the evidence has 2, 3, 5, 7 or 8 cells.

## Choice points
- `dot-reach`: how many dots each end of a side sends
    - `concept`: as many as fit up to the middle of the gap
    - `$CappedReach`: replaces `dotted-sides`. Each end dots at most `reach_cap` (2) cells, at distances 1, 3, …, 2·`reach_cap`−1 from its ring, and still only on its own half. Undefined where the concept is undefined. Fits every pair. Witness `long-side`, a gap of 10 cells: the concept dots rows 4, 6, 8, 9, 11, 13, and this branch dots only 4, 6, 11, 13. It breaks no scene claim, stands at the stored assignment, `ordinary`, verdict `concept`.
- `arm-clip`: whether one end's dots stop where the other end's half begins
    - `concept`: they stop at the middle; a cell takes its parity from the nearer ring
    - `$UnclippedArm`: replaces `dotted-sides`. Each end's dots run from its ring across the whole gap, the side takes the union of both ends' dots, and the rings are drawn over them. Fails Fit at train1: col 2 rows 5–12 come out fully dotted, where the output dots only 5, 7, 10, 12.
- `dot-ends`: which ends of a side the alternation counts from
    - `concept`: both ends
    - `$OneEndAlternation`: replaces `dotted-sides`. The dots alternate from the ring at one end, held in a stored direction per axis, across the whole gap. Fails Fit at train0: the gap at row 2 cols 3–4 gets only col 3 (from the left) or only col 4 (from the right), and the output dots both.
- `dot-anchor`: what a dot's distance is counted from
    - `concept`: the nearer ring; dots at odd distances
    - `$MarkerParity`: replaces `dotted-sides`. The distance is counted from the nearer marker, with dots at even distances. Fails Equivalence: on every input a cell's distance to the nearer marker is its distance to the nearer ring plus one, because the ring is fixed at 3×3, so the two models agree at every assignment. No witness exists.
- `ring-color`: which color a marker's ring takes
    - `concept`: the other of the two marker colors
    - `$PartnerColor`: replaces `swap-ring`. The ring takes the color of the marker on the same line along `partner_axis` (`AXIS_V` or `AXIS_H`). The case runs every value of `partner_axis` and is undefined on an input where those values give different outputs. Also undefined where the concept is undefined, except that it needs no two-color scene. Fits every pair. Witness `row-colored`: the markers in each row share a color, on a rectangle taller than wide. The two values give two grids: the concept's grid, and one where each row partner rings its marker in the marker's own color as a solid 3×3 block. So the case is undefined there. It breaks `diagonal-colors`, stands at the stored assignment, `foreign`, verdict `concept`. It breaks the input invariant that the two markers on each diagonal share a color.
    - `$NearestMarkerColor`: replaces `swap-ring`. The ring takes the color of the nearest other marker. Undefined on a square rectangle whose two side partners differ in color. Fits every pair. Witness `row-colored`: the nearest marker is the row partner, so each top marker gets a solid 3×3 block of 2 and each bottom marker one of 3. It breaks `diagonal-colors`, stands at the stored assignment, `foreign`, verdict `concept`. It breaks the same invariant as `$PartnerColor`.
    - `$DiagonalPartnerColor`: replaces `swap-ring`. The ring takes the color of the marker diagonally opposite, which is the marker's own color, so every box becomes a solid 3×3 block. Fails Fit at train0: the ring around (2,1) comes out 2 where the output has 3.
    - `$StoredRingMap`: replaces `swap-ring`. A stored table maps each marker color to a ring color. Fails Fit at train2: key 2 needs ring 3 in train0 and ring 4 in train2. The test also needs 4→1 and 1→4 against train2's 4→2 and train1's 1→8.
- `background`: where the field color comes from
    - `concept`: stored, `0`
    - `background=DominantColor`: derives the field as each input's commonest color. Fits every pair. Witness `background=DominantColor`, the same scene on a field of 7. At the stored 0 every cell counts as a marker and every other case is undefined. This branch draws the rings and dots on the 7 field. It breaks `four-corner-markers` (a field of `background` 0), stands at the stored assignment, `variant`, verdict `background=DominantColor`. It breaks the input invariant that every field is 0.
    - `background=SharedColor`, `background=RarestColor`: on train0 alone these give {0, 2, 3} and {2, 3}. At a marker color the scene holds far more than four marked cells, so the model is undefined: fails Fit at train0.
- `dot_color`: where the dot color comes from
    - `concept`: stored, `5`
    - `dot_color=OutNewColor`, `dot_color=AnyOutNewColor`, `dot_color=ChangedColor`, `dot_color=UnchangedColor`, `dot_color=VanishedColor`: each reads train outputs. On one input, with `ex_out` empty, they give no value, so the model is undefined: fails Fit at train0.
    - `dot_color=SharedColor`, `dot_color=DominantColor`, `dot_color=RarestColor`: on train0 alone these give {0, 2, 3}, 0 and {2, 3}. None of them is 5, so the sides are not dotted 5: fails Fit at train0.
- `dot-reach` & `arm-clip`: the case that takes both runs `reach_cap` dots from each ring without the cut at the middle, rings drawn over, and fits every pair. Witness `four-cell-gap`, a gap of 4 cells: the concept and `$CappedReach` dot the two cells next to the rings, and this case dots all four. It breaks no scene claim, stands at the stored assignment, `ordinary`, verdict `concept`.
- `dot-reach` & `dot-ends`, `dot-reach` & `dot-anchor`, `dot-reach` & `ring-color`, `dot-reach` & `background`, `dot-reach` & `dot_color`, `arm-clip` & `dot-ends`, `arm-clip` & `dot-anchor`, `arm-clip` & `ring-color`, `arm-clip` & `background`, `arm-clip` & `dot_color`, `dot-ends` & `dot-anchor`, `dot-ends` & `ring-color`, `dot-ends` & `background`, `dot-ends` & `dot_color`, `dot-anchor` & `ring-color`, `dot-anchor` & `background`, `dot-anchor` & `dot_color`, `ring-color` & `background`, `ring-color` & `dot_color`, `background` & `dot_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A ring wider than 3×3, or dots every third cell, as a parameter: no variant task the generator produces changes the ring size or the dot period, because D4 and color permutations keep both. So neither is task data, and no assignment separates `$MarkerParity` from the concept.
- A derived `reach_cap`, `partner_axis` or dot period: no proposer gives a number or an axis from one input that these could read.

## Tickets filed
- none
