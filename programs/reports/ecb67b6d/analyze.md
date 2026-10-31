# ecb67b6d

## Concept
- Fits every pair, test0 included, at `mark_color` 5, `fill_color` 8, `min_run` 3 (`work/task/ecb67b6d/check_concept.py`). `min_run` 2 fails train0 (the clumps at (0,0) and (0,2), with runs of 2, would recolor), and 4 fails train1 (the clump at (0,3), whose longest run is 3, would stay). So the pairs fix the threshold.
- No witness has verdict `other`. The generator's rule is the concept's rule: each 8-connected clump of mark cells that holds a straight diagonal run of at least three cells, on either diagonal axis, is recolored whole. That rule has a relational form (8-connected components plus corner-contact chains along one diagonal axis), so no approximation stands in for it.
- The program goes through every value of the diagonal-axis type (both axes). No pair separates the axes, since train1 has only an anti-diagonal run and train2's (0,8) and (8,0) clumps have only main-diagonal runs.

## Choice points
- `recolor-unit`
    - `concept`: every cell of the 8-connected clump that holds a run (`clumps`, `recolor-clump`)
    - `$RunFourComps`: replaces `clumps` and `recolor-clump`. It recolors each 4-connected component that holds a cell of a run. Same parameters, defined on every input. Fails Fit at test0: it leaves (2,9), (7,17) and (13,11)–(13,13) as 5, and these cells join a run only through a corner contact with a cell off the run.
    - `$RunCellsOnly`: replaces `recolor-clump`. It recolors only the cells of runs. Same parameters, defined on every input. Fails Fit at train0, where it leaves (2,6), (3,6), (4,6) as 5.
- `run-line`
    - `concept`: a run lies along either diagonal axis
    - `$RunOneAxis`: replaces `diagonal-run`. A run lies along one diagonal axis, stored as a new parameter `run_axis`. Defined on every input. Fails Fit: at the main diagonal it fails train1 ((0,3), (1,1), (1,2), (2,0), (2,1) stay 5), and at the anti-diagonal it fails train2 (the clumps at (0,8) and (8,0) stay 5).
    - `$RunAnyLine`: replaces `diagonal-run`. A run lies along any of the four line families, rows and columns included. Defined on every input. Fails Fit at train0, where it recolors the column (0,0)–(5,0) and its clump.
- `run-step`
    - `concept`: every corner contact along the line extends a run
    - `$PureDiagonalRun`: replaces `diagonal-run`. A corner contact extends a run only when neither of the two side neighbors the cells share is a mark cell. Defined on every input. Fails Fit at train1: the step (1,2)–(2,1) shares the mark (1,1), so (0,3), (1,1), (1,2), (2,0), (2,1) stay 5.
- `run-length`
    - `concept`: a run holds at least `min_run` cells
    - `$ExactRun`: replaces `diagonal-run`. A run holds exactly `min_run` cells. Same parameters, defined on every input. Fails Fit at train0, where the run (0,7)–(3,4) holds 4 cells and its clump stays 5.
- `mark_color`
    - `concept`: `mark_color` is stored
    - `mark_color=RarestColor`: replaces the stored `mark_color` with the input's rarest color. Defined on every input, and on a tie it takes each tied color. Fits every pair (5 is the rarest color of every input). Witness `mark_color=RarestColor`, at the stored assignment. It breaks `marks-on-field`. Plausibility `borderline`, verdict `concept`. The invariant it breaks: in every input the mark color has fewer cells than the background.
- `recolor-unit` & `run-line`, `recolor-unit` & `run-step`, `recolor-unit` & `run-length`, `recolor-unit` & `mark_color`, `run-line` & `run-step`, `run-line` & `run-length`, `run-line` & `mark_color`, `run-step` & `run-length`, `run-step` & `mark_color`, `run-length` & `mark_color`: the two branches' changes applied together (under `$RunAnyLine` & `$PureDiagonalRun`, the purity test applies to the corner contacts and leaves row and column steps as they are)

## Open parameters
- none

## Not formed
- `fill_color` derived: no derivation that reads one input and no output gives 8, a color no input holds. OutNewColor and AnyOutNewColor read the outputs, which are empty under `@derive`, so the branch would be undefined on every input.
- `mark_color` derived by DominantColor, SharedColor, VanishedColor, ChangedColor or UnchangedColor: on one input with no output, each gives 7 alone or both 5 and 7. With 7 as a mark color, the background clump of train0, which holds diagonal runs such as (2,2)–(4,4), recolors, so the branch fails Fit at train0.
- `min_run` derived: no proposer gives 3 from an input.
- `background` read by the program: no rule reads it, so it stays a scene parameter.
- A clump-size or edge-contact criterion in place of `diagonal-run`: train2 leaves clumps of 8 cells (the block at (1,0)) and 6 cells (the zigzag at (9,4)) unchanged, and recolors clumps of 3 and 4 cells, and clumps on both sides touch an edge. So no value of either criterion separates them.

## Tickets filed
- none
