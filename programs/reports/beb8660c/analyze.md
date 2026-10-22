# beb8660c

## Concept
- The concept fits every pair. No witness has the verdict `other`.
- The concept is undefined where two bars of different colors have the same length, because the order between those two bars is free. The scene claim `lengths-one-to-width` excludes such inputs. The generator applies the rule as the concept file gives it: the bars are sorted by length, longest at the `fall_dir` edge, stacked with no gap rows, and each bar touches the `align_side` edge.

## Choice points
- `item`: what one moving unit is
    - `concept`: a bar, which is a one-row run of one color
    - `$RowUnit`: replaces `bars` and `sort-by-length`. Each non-empty row is one unit. Its length is the count of its non-`bg` cells, and its cells keep their left-to-right order and pack against `align_side`. It is undefined where two rows with different content have the same count. It fits every pair. Witness `two-bars-one-row`: it breaks `bars`; plausibility `borderline`, because every input has at most one bar on a row; verdict `concept`.
- `placement`: the row each unit lands on
    - `concept`: units are stacked from `fall_dir` with no gap rows, ranked by length
    - `$RowByLength`: replaces `sort-by-length` and `stack-at-edge`. A unit of length L lands width − L rows from the `fall_dir` edge. It is undefined where two units land on one row or a unit lands outside the frame. It fits every pair. Witness `missing-length`: it breaks `lengths-one-to-width`; plausibility `variant`, because in every input the bar lengths are exactly 1 to the width; verdict `concept`.
    - `$KeepOrder`: replaces `sort-by-length`. Units are stacked from `fall_dir` with no gap rows, in their input row order. It fails Fit at train0, train1, train2 and test0.
- `base`: what happens to the `base_color` bar
    - `concept`: it is ranked like every other bar
    - `$BaseStays`: replaces `base-bar` and `sort-by-length`. The program reads `base_color` (8). The one `base_color` unit takes the bottom row, against `align_side`, and the other units stack on it by length. It is undefined where the number of `base_color` units is not one. It fits every pair. Witness `short-base`: it breaks `base-bar`; plausibility `borderline`, because in every input the bottom row is a full-width 8 bar; verdict `concept`.
- `bg`: the background color
    - `concept`: stored, 0
    - `bg=DominantColor`: replaces the stored `bg` with the commonest colors of the input. It fails Fit at train2, where 0 and 8 tie with 3 cells each.
- `item` & `placement`, `item` & `base`, `item` & `bg`, `placement` & `base`, `placement` & `bg`, `base` & `bg`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Order among bars of equal length: this is a tiebreak, so it introduces no case.
- Bars kept in their input columns, or aligned to the left: train0 moves each bar against the right edge, so a reading that keeps the columns fails Fit at every pair. `align_side` is an orientation parameter, and the pairs fix its value.
- Rigid-body gravity, with each bar slid right and then dropped under `Gravity`: every slid bar covers the right column, so the bars keep their input order. That is the model of `$KeepOrder`.
- Units as 4-connected components of all non-`bg` cells: train0 rows 6 and 7 (the 6 bar and the 4 bar) touch, so the components merge into one unit, which fails Fit at train0.
- Shortest bar at the `fall_dir` edge: every pair puts the longest bar on the bottom row, so this fails Fit.

## Tickets filed
- none
