# d304284e

## Concept
- The concept fits every pair: train0, train1 and test0 each come out exact. Each rule has a relational form, and no witness has the verdict `other`.
- Every input is 23 rows by 28 columns and holds one 3-column-wide shape in the top half, with the most room to its right. The witnesses below that break one of these invariants say which one.

## Choice points
- `march-direction`
    - `concept`: `march_dir` is stored (right)
    - `$MarchToRoom`: replaces the stored `march_dir` of `march` with a derivation. The run goes the way in which the ink's bounding box has the most cells to the grid edge, and on a tie each such way, with the output holding each grid. `march_dir` is dropped. The model is undefined where the derived way lies on the axis of `branch_dir`. It fits every pair. Witness `march-to-room`: the shape sits 5 columns from the right edge and 20 from the left. It breaks `room-ahead`. Plausibility `borderline`, verdict `$MarchToRoom`. It breaks the invariant that every shape has the most room to its right.
- `branch-direction`
    - `concept`: `branch_dir` is stored (down)
    - `$BranchToRoom`: replaces the stored `branch_dir` of `branch` with a derivation. Of the two ways across `march_dir`, the drops go the way with more cells between the ink's bounding box and the grid edge, and on a tie both ways. `branch_dir` is dropped. The model is defined on every input. It fits every pair. Witness `branch-to-room`: the H shape sits at rows 14–18, with 4 rows below it and 14 above. It breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariant that every shape lies in the top half, with more rows below it than above.
- `march-step`
    - `concept`: the step along the run is the shape's extent along `march_dir` plus `gap`, and that `gap` is shared with the drops
    - `$MarchGap`: replaces `march`. The step is the shape's extent plus a gap of its own, `march_gap` (1), and `gap` is read on the drop axis alone. The model is defined on every input. It fits every pair. Witness `march-gap`: train1's input at `march_gap` = 2. It breaks no scene claim. Plausibility `ordinary`, verdict `$MarchGap`.
    - `$StoredStride`: replaces `march`. The step is a stored `march_stride` (4), which takes the place of the shape's extent plus `gap`, and `gap` is read on the drop axis alone. The model is defined on every input. It fits every pair. Witness `stored-stride`: a ring 4 columns wide, whose copies touch under this branch. It breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariant that every shape is 3 columns wide.
- `marked-copies`
    - `concept`: a copy is marked when its number, with the shape as copy 1, is a multiple of `period`
    - `$MarkPhase`: replaces `mark-every-period`. A copy is marked when its number is congruent to a stored `mark_phase` (0) modulo `period`. The model is defined on every input. It fits every pair. Witness `mark-phase`: train0's input at `mark_phase` = 1, where copies 1 and 4 are marked, the shape among them. It breaks no scene claim. Plausibility `ordinary`, verdict `$MarkPhase`.
    - `$MarkSet`: replaces `mark-every-period` with a stored set `marked_numbers` = {3, 6} of copy numbers. `period` is dropped. The model is defined on every input. It fits every pair, and every test copy number occurs in train1. Witness `mark-set`: a 2-wide shape at column 1, so the run holds 9 copies, and copy 9 is marked under the concept and not under this branch. It breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariants that every shape is 3 columns wide and that every run holds at most 7 copies.
- `march-extent`
    - `concept`: the copies repeat toward `march_dir` only
    - `$MarchBothWays`: replaces `march`. The copies repeat toward `march_dir` and away from it, and each way is numbered from the shape. It fails Fit at train0: the copy at `train0 output rows 4–8, cols 1–3` is `0` there.
- `branch-extent`
    - `concept`: the drops go toward `branch_dir` only
    - `$BranchBothWays`: replaces `branch`. The drops go toward `branch_dir` and away from it. It fails Fit at train0: the drop at `train0 output rows 0–2, cols 13–15` and `cols 25–27` is `0` there.
- `edge-copies`
    - `concept`: a copy that the grid edge cuts is drawn in part
    - `$WholeCopiesOnly`: replaces `march` and `branch`. Only copies that lie whole inside the grid are drawn. It fails Fit at train0: `train0 output row 22`, cols 13, 15, 25 and 27, is `6`.
- `unit`
    - `concept`: all the ink is copied as one unit
    - `$PerObject`: replaces `march`, `mark-every-period` and `branch`. Each 8-connected object runs, is numbered, is marked and drops on its own, with its own extents. The model is undefined where two objects' copies put different colors on one cell. It fits every pair. Witness `per-object`: train1's ring with a separate 3-cell bar at row 12, cols 3–5. It breaks `one-shape`. Plausibility `borderline`, verdict `$PerObject`. It breaks the invariant that every input holds one object.
- `mark-paint`
    - `concept`: every cell of a marked copy and of its drops takes `mark_color`
    - `$RecolorShapeColor`: replaces `mark-every-period` and `branch`. Only the cells of `shape_color` take `mark_color`, and every other cell keeps its color. `shape_color` becomes a parameter. The model is defined on every input. It fits every pair. Witness `recolor-shape-color`: train1's ring with a center of color 2. It breaks `one-shape`. Plausibility `borderline`, verdict `concept`. It breaks the invariant that every shape is of one color.
- `background`
    - `concept`: `background` is stored (0)
    - `background=DominantColor`: `background` is derived as the commonest input color, and on a tie as each such color. The model is defined on every input. It fits every pair. Witness `background=DominantColor`: a 3×5 grid in which the ring's 8 cells outnumber the 7 cells of `0`. It breaks `room-ahead`. Plausibility `foreign`, verdict `concept`. It breaks the invariants that every input is 23×28 and that the background covers most of each input.
- `march-direction` & `branch-direction`, `march-direction` & `march-step`, `march-direction` & `marked-copies`, `march-direction` & `march-extent`, `march-direction` & `branch-extent`, `march-direction` & `edge-copies`, `march-direction` & `unit`, `march-direction` & `mark-paint`, `march-direction` & `background`, `branch-direction` & `march-step`, `branch-direction` & `marked-copies`, `branch-direction` & `march-extent`, `branch-direction` & `branch-extent`, `branch-direction` & `edge-copies`, `branch-direction` & `unit`, `branch-direction` & `mark-paint`, `branch-direction` & `background`, `march-step` & `marked-copies`, `march-step` & `march-extent`, `march-step` & `branch-extent`, `march-step` & `edge-copies`, `march-step` & `unit`, `march-step` & `mark-paint`, `march-step` & `background`, `marked-copies` & `march-extent`, `marked-copies` & `branch-extent`, `marked-copies` & `edge-copies`, `marked-copies` & `unit`, `marked-copies` & `mark-paint`, `marked-copies` & `background`, `march-extent` & `branch-extent`, `march-extent` & `edge-copies`, `march-extent` & `unit`, `march-extent` & `mark-paint`, `march-extent` & `background`, `branch-extent` & `edge-copies`, `branch-extent` & `unit`, `branch-extent` & `mark-paint`, `branch-extent` & `background`, `edge-copies` & `unit`, `edge-copies` & `mark-paint`, `edge-copies` & `background`, `unit` & `mark-paint`, `unit` & `background`, `mark-paint` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- The drop direction stored as a turn sense from `march_dir`: the pairs (`march_dir`, `branch_dir`) map one to one onto the pairs (`march_dir`, sense), so that model is equivalent to the concept.
- Marks counted from the far edge of the run, or set by a column residue: train0 marks the last copy and train1 marks the next-to-last one, and the marked columns 13 and 25 against 11 and 23 share no residue modulo 12. No assignment fits both train pairs.
- One stored stride on both axes: the drops step 6 rows in train0 and 4 in train1. No stored value fits both train pairs.
- Drops in the shape's own colors: every drop is `6` in each pair's output.
- `mark_color` derived as a new output color (`OutNewColor`): `6` occurs in no input, and that derivation reads train outputs only. It gives no value on an input alone, so the branch is undefined on every pair's input.

## Tickets filed
- none
