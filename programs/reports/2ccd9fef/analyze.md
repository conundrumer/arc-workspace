# 2ccd9fef

## Concept
- The concept case fits every pair: `probe.py` gives each train and test output.
- No witness has the verdict `other`.
- The generator applies `next-step` as: each object goes on growing and moving the way the filled panels show. The concept's rule approximates this: it pairs the objects of neighboring panels by the one pairing under which every step is steady, and it advances each object as one whole stretch.
- The concept case is undefined on `two-color-split` and `staircase-growth`, where an object does not stretch as one whole. It is also undefined on `crossing-pair`, where two pairings of two like bars each give a steady step. On each of these inputs the verdict is the branch whose model is defined.

## Choice points
- `step-unit`: what one step acts on
    - `concept`: each object, a 4-connected set of object cells, changes by one stretch along one axis, with its two ends each moving a fixed count of cells.
    - `$PerLineRuns`: replaces `steady-step` and `next-step`. Each run of object cells along the growth axis changes by its own steady stretch, line by line, and is paired with the run of the same rank on its line in the next panel. It is undefined where the run counts of a line differ between panels. It fits every pair, and its witness is `staircase-growth`. That witness breaks `steady-step` and also the invariant of the inputs that all lines of an object grow by one count each step. Plausibility `variant`, verdict `$PerLineRuns`.
    - `$FrameMotions`: replaces `steady-step` and `next-step` with 351d6448's reading. The whole panel changes by one motion of one kind (content translating, a run growing from its end, or a front advancing), with one count for every front. It fails Fit at test1: the T's stem front moves 2 cells per step, its bar moves 1 cell, and the 6 blocks grow the other way.
        - `object`: what an object is
            - `concept`: a 4-connected component of object cells, of any colors.
            - `$ColorClassObjects`: replaces `steady-step` and `next-step`. An object is the set of object cells of one color. It fits every pair, and its witness is `two-color-split`. That witness breaks `steady-step` and also the invariant of the inputs that every object's colors stretch together. Plausibility `variant`, verdict `$ColorClassObjects`.
            - `$EightAdjacentObjects`: replaces `steady-step`. An object is an 8-connected component. It fails Fit at test1: in the second panel the T's stem touches both 6 blocks at corners, so the object counts of the panels differ.
            - `$SingleColorComponents`: replaces `steady-step`. An object is a 4-connected component of one color. It fails Fit at test0: each 6 cell is a component of its own, and their count grows from panel to panel.
            - `$WholePanelObject`: replaces `steady-step`. All object cells of a panel form one object. It fails Fit at train0: the 3 block grows to the right and the 8 bracket to the left, so their union does not stretch as one whole.
        - `object-step`: how an object changes in one step
            - `concept`: the object stretches by repeating its periodic run of lines, and its two ends each move a fixed count of cells.
            - `$Smear`: replaces `steady-step` and `next-step`. The object in the next panel is the union of the object and the object translated by one offset. It fails Fit at train0: the 8 bracket's middle column does not widen.
            - `$AddedCellsRepeat`: replaces `steady-step` and `next-step` with 20a9e565's reading. Each figure holds the one before it with its colors changed by one map, plus the cells its step adds. It fails Fit at train1: the 4 at (2,4) becomes 1 while the 4 at (3,4) stays 4, so no one color map carries the first panel into the second.
        - `pairing`: how the objects of neighboring panels pair
            - `concept`: the one pairing under which every object's steps are steady; where several such pairings give different outputs, the concept is undefined.
            - `$PairByOverlap`: replaces `next-step`. Each object pairs with the object of the next panel that it overlaps most. It is undefined where an object overlaps no object of the next panel. It fits every pair, and its witness is `crossing-pair`, which breaks no scene claim. That witness breaks the invariant of the inputs that no two objects of a panel share one shape on one line along the growth axis. Plausibility `variant`, verdict `$PairByOverlap`.
- `recolor`: how an object's colors change from panel to panel
    - `concept`: one fixed permutation, read from every step.
    - `$ColorTwoBack`: replaces `steady-step` and `next-step`. The next panel's colors are those of the panel before the last filled one, through the inverse of the last step's color map. It fits every pair, and its witness is `color-cycle`, which breaks no scene claim. That witness breaks the invariant of the inputs that each recoloring swaps two colors. Plausibility `variant`, verdict `concept`.
    - `$NoRecolor`: replaces `steady-step`. Colors do not change. It fails Fit at test0, where the object alternates between 1 and 4.
    - `color_step=stored`: replaces `steady-step`. The color permutation is a stored value in place of the one read from the panels. It fails Fit at test0: train1 keeps 1 and 4, and test0 swaps them, so no one stored map fits both.
- `step-source`: which steps the step is read from
    - `concept`: every step between neighboring filled panels, all equal.
    - `$LastStepOnly`: replaces `steady-step`. The step and its color map come from the last two filled panels alone, and a color that map does not carry stays. It fails Fit at test0: the last step carries 1 to 4 and leaves 4 unmapped, so the output keeps 4 where the expected output has 1.
- `time-order`: which end of the strip the sequence runs toward
    - `concept`: toward the blank end panel, read from the input.
    - `time_dir=stored`: replaces `blank-end-panel`. A stored direction on each axis, toward the bottom and toward the right, gives the end of the strip. It fits every pair, and its witness is `time_dir=stored`, at the stored assignment, which breaks no scene claim. That witness breaks the invariant of the inputs that the blank panel is at the bottom or right end. Plausibility `variant`, verdict `concept`. It fails Subsumption: where it is defined, its end is the blank end and its output is the concept's.
- `panel-split`: how the strip is cut into panels
    - `concept`: the split into equal panels along the long axis under which every panel shows the blank end panel's background off the object colors.
    - `panel_count=stored`: replaces `panel-strip`. The panel count is a stored value. It fails Fit at test0, which has 5 panels where the other pairs have 3.
- `step-unit` & `recolor`, `step-unit` & `step-source`, `step-unit` & `time-order`, `step-unit` & `panel-split`, `recolor` & `step-source`, `recolor` & `time-order`, `recolor` & `panel-split`, `step-source` & `time-order`, `step-source` & `panel-split`, `time-order` & `panel-split`, `object` & `object-step`, `object` & `pairing`, `object-step` & `pairing`, `object` & `recolor`, `object` & `step-source`, `object` & `time-order`, `object` & `panel-split`, `object-step` & `recolor`, `object-step` & `step-source`, `object-step` & `time-order`, `object-step` & `panel-split`, `pairing` & `recolor`, `pairing` & `step-source`, `pairing` & `time-order`, `pairing` & `panel-split`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A panel split by another period: every split other than the true one cuts the blank panel into pieces. The piece before the last one is then blank, and `filled-panels` fails, so no input the scene claims allow has a second split.
- Colors chosen by the parity of a panel's place in the strip: on every input, the panel two before the slot has the slot's parity, so this reading gives `$ColorTwoBack`'s model.
- The order in which objects that meet in the next panel are drawn: no reading orders the objects, and the concept and every branch are undefined where two objects put different colors on one cell.

## Tickets filed
- 4-39_task_2ccd9fef_analyze.md
