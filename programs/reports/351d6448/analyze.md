# 351d6448

## Concept
- It fits every pair: the step is one column in train0, two in train1 and one in the test, and `probe.py` gives each pair's output.
- Its rule approximates the rule as the generator applies it: each frame advances one motion by a fixed count of cells, and the motion is an object translating (train0), a run extending from its end (train1), or the edge of a color region advancing over a shape (test). The concept moves the first change instead, and on witness `front-start` (plausibility `ordinary`) it leaves the new edge column's row 0 cell `2`, because the first change did not reach row 0. `$ObjectMotion` states the generator's rule.
- No witness with verdict `other` is left to it.

## Choice points
- `change_reading`
    - `concept`: the first change, read cell by cell as recolors, moved by the step and applied only where a cell holds the color it recolors from
    - `$UnfilteredChange`: replaces `steady-step` and `next-frame`: the moved change recolors its cells whatever color they hold; undefined where the panels do not follow that; fails Fit at test0, whose panels it cannot follow (it would recolor `0` cells of the shape's gaps)
    - `$LastChangeOnly`: replaces `next-frame`: the output moves the change between the last two panels by one step; fails Fit at test0, where it recolors only (2,5) and leaves (1,5) `2`
    - `$LineRecolor`: replaces `steady-step` and `next-frame`: the change is read per column, and the column it reaches recolors every cell of the from color; undefined where the panels do not follow that; fails Fit at train0 and train1, where it recolors the `0` cells of rows 0 and 2 too
    - `$ObjectMotion`: replaces `steady-step` and `next-frame`: the panels show one motion of a kind read from them, an object translating, a run extending from its end, or the edge of a color region advancing over a shape, by a fixed count of cells per frame, and the output advances it one step past the last panel; undefined where the panels show none of those kinds; fits every pair; witness `front-start`, plausibility `ordinary`, verdict `$ObjectMotion`
- `step_amount`
    - `concept`: derived per input, from the panels
    - `$StoredStep`: replaces `steady-step`: a stored count of cells per frame; fails Fit, since train0 steps one column and train1 two
- `step_direction`
    - `concept`: derived per input, along the axis across `panel_axis`, toward either end
    - `$StoredDirection`: replaces `steady-step`: a stored direction of the step, `R`, its amount derived; undefined where no step toward that direction follows the panels; fits every pair; witness `static-tail`, which breaks `steady-step` (nothing changes after the second panel), plausibility `foreign`, verdict `$StoredDirection`, breaking the invariant that each panel differs from the one before it
    - `$AnyOffset`: replaces `steady-step`: the step is any offset in the panel, along either axis or both; fails Fit at test0, where the offset one row down and one column right also follows the panels and gives a second grid with (1,5) and (2,5) left `2`
- `step_check`
    - `concept`: the step is the one that every panel follows
    - `$StepFromFirstTwo`: replaces `steady-step`: the step is the one that the second change follows from the first, and the later panels are not checked; fits every pair; witness `uneven-steps`, which breaks `steady-step`, plausibility `foreign`, verdict `other`, breaking the invariant that every frame moves by one step
- `step_scope`
    - `concept`: one change and one step for the whole panel
    - `$StepPerLine`: replaces `steady-step` and `next-frame`: each line across `panel_axis` has its own change and its own step; fits every pair; witness `two-speeds`, which breaks `steady-step`, plausibility `variant`, verdict `$StepPerLine`, breaking the invariant that each input holds one moving thing
- `divider_color`
    - `concept`: stored, `5`
    - `$DividerColorFromLines`: replaces `panels`: derived per input as the color whose full lines along `panel_axis` cut the grid into equal panels; undefined where no color does; fits every pair; witness `divider-8`, which breaks `panels`, plausibility `variant`, verdict `$DividerColorFromLines`, breaking the invariant that the dividers are `5`
- `divider_width`
    - `concept`: stored, `1`
    - `$DividerWidthFromLines`: replaces `panels`: derived per input as the width of the runs of full `divider_color` lines; undefined where the runs differ in width; fits every pair; witness `divider-2-wide`, which breaks `panels`, plausibility `variant`, verdict `$DividerWidthFromLines`, breaking the invariant that each divider is one line
- `panel_count`
    - `concept`: stored, `4`
    - `$AnyPanelCount`: replaces `panels`: any count of three or more panels, read from the input; fits every pair; witness `five-panels`, which breaks `panels`, plausibility `variant`, verdict `$AnyPanelCount`, breaking the invariant that each input has four panels
- `change_reading` & `step_direction`, `change_reading` & `step_check`, `change_reading` & `step_scope`, `change_reading` & `divider_color`, `change_reading` & `divider_width`, `change_reading` & `panel_count`, `step_direction` & `step_check`, `step_direction` & `step_scope`, `step_direction` & `divider_color`, `step_direction` & `divider_width`, `step_direction` & `panel_count`, `step_check` & `step_scope`, `step_check` & `divider_color`, `step_check` & `divider_width`, `step_check` & `panel_count`, `step_scope` & `divider_color`, `step_scope` & `divider_width`, `step_scope` & `panel_count`, `divider_color` & `divider_width`, `divider_color` & `panel_count`, `divider_width` & `panel_count`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A count of frames ahead other than one: every output is the frame right after the last panel, and no reading of the pairs gives another count.
- A background color in the scene: the test's panels hold more `2` than `0`, so no field color holds of every input, and no rule reads one.
- A sequence other than a constant step, such as a run length that doubles: train1's lengths 2, 4, 6, 8 and train0's columns 1, 2, 3, 4 follow a constant step and no other progression.
- An output frame other than one panel: every output is one panel in size.

## Tickets filed
- 3-3_task_351d6448_analyze.md
