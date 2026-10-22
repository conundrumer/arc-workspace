# d06dbe63

## Concept
- Fits every train and test pair (`probe.py`). Each claim has a relational form, and the rule is exact, so it approximates nothing.
- No witness has verdict `other`.
- In each input the marker sits in the middle of a vertical run of 5 cells, and every other run is 3 cells. So the output is two arms that each start at the marker, and is not one staircase that runs through the marker.
- The bottom-left arm is the top-right arm turned a half turn about the marker. The mirror image across the main diagonal (`$MirrorArms`) fails train0.

## Choice points
- `leg-lengths`: whether the two legs of a step share one length
    - `concept`: one `leg` (2) for both legs
    - `$UnequalLegs`: replaces `staircase`. The second leg has its own length `leg2` (2), and the first leg reads `leg`. Defined wherever the concept is. Fits every pair. Witness `unequal-legs`: train0 input at `leg2` = 3. It breaks no scene claim. Plausibility `ordinary`, verdict `$UnequalLegs`.
- `arm-first-axis`: how the two arms' first axes relate
    - `concept`: the arms share `first_axis` (V), so each arm is the other turned a half turn
    - `$FirstAxisPerCorner`: replaces `staircase`. `corner_first_axis` stores a first axis for each corner (top-right: V, bottom-left: V). Defined wherever the concept is. Fits every pair. Witness `first-axis-per-corner`: train0 input with bottom-left set to H. It breaks no scene claim. Plausibility `ordinary`, verdict `$FirstAxisPerCorner`.
    - `$MirrorArms`: replaces `staircase`. The arm toward the second corner is the first arm reflected across the axis through the marker that swaps the two corners, so it starts on the other axis. Fails Fit at train0: its bottom-left arm starts at (3,3), (3,2), and the output starts it at (4,4), (5,4).
    - `$FirstAxisNearerEdge`: replaces `staircase` and derives each arm's first axis as the axis of the nearer of the corner's two edges. Fails Fit at train0: the marker (3,4) is nearer the left edge than the bottom edge, and the output's bottom-left arm starts downward.
- `corners`: which corners the arms climb toward
    - `concept`: the two corners of `diag_axis` (the anti-diagonal)
    - `$CornerSet`: replaces `staircase`. `corners` stores a set of corners ({top-right, bottom-left}) in place of `diag_axis`. Defined wherever the concept is. Fits every pair. Witness `corner-set`: train0 input at `corners` = {top-right}. It breaks no scene claim. Plausibility `ordinary`, verdict `$CornerSet`.
- `step-form`: how one step of an arm is given
    - `concept`: two straight legs from `first_axis` and `leg`
    - `$StoredStep`: replaces `staircase`. `step` stores the cells of one step relative to its start (2 up, then 2 right). The bbox corner opposite the start is the next step's start, and the second arm repeats the step turned a half turn. Defined wherever the concept is. Fits every pair. Witness `stored-step`: train0 input with a step of 3 up and 1 right. It breaks no scene claim. Plausibility `ordinary`, verdict `$StoredStep`.
- `edge`: where an arm ends at the grid edge
    - `concept`: each cell is drawn while it is in the grid, and the arm ends once a step has no cell in the grid (`clip`)
    - `$WholeLegs`: replaces `clip`. A leg is drawn only when all its cells are in the grid. Fails Fit at train0: the output draws the cut leg's in-grid cell at (0,6).
    - `$WrapEdges`: replaces `clip`. The arm wraps to the opposite edge and ends when it returns to a step start it has already left. Fails Fit at train0: the top-right arm wraps from (-1,6) to (12,6), and the output has 0 at (12,6).
- `marker-count`: what the model does when the input does not hold exactly one marker
    - `concept`: an arm pair leaves each marker
    - `$SingleMarker`: adds the condition that the input holds exactly one non-background cell, and is undefined elsewhere. Fits every pair. Witness `two-markers`: two 8 cells at (3,2) and (9,8) whose arms do not meet. The concept draws both staircases, and `$SingleMarker` is undefined. It breaks `one-marker`. Plausibility `variant`, verdict `concept`. Breaks the input invariant that each input holds one non-background cell. It fails Subsumption: it reads the concept's parameters, and wherever it is defined its output is the concept's.
- `marker-selection`: which cells are markers
    - `concept`: every non-background cell (`marker_color` is a scene parameter)
    - `$MarkerByColor`: replaces the marker reading in `staircase`. Markers are the cells of `marker_color` (8), so the program reads `marker_color`. Defined wherever the concept is. Fits every pair. Witness `marker-color`: train0 input with the marker recolored 3. `$MarkerByColor` returns the input, and the concept draws the staircase. It breaks `one-marker` at `marker_color` = 8. Plausibility `variant`, verdict `concept`. Breaks the input invariant that the one non-background cell is 8.
- `blocked-path`: what an arm does when it reaches a non-background cell
    - `concept`: it passes the cell, keeps that cell's color, and goes on
    - `$StopAtCell`: replaces `staircase`. An arm ends at the first non-background cell it reaches. Defined wherever the concept is. Fits every pair. Witness `crossing-paths`: 8 cells at (8,4) and (6,5), each on an arm of the other. It breaks `one-marker`. Plausibility `borderline`, verdict `concept`. Breaks the input invariant that each input holds one non-background cell.
- `leg-lengths` & `arm-first-axis`, `leg-lengths` & `corners`, `arm-first-axis` & `corners`, `marker-selection` & `leg-lengths`, `marker-selection` & `arm-first-axis`, `marker-selection` & `corners`, `marker-selection` & `step-form`, `marker-selection` & `marker-count`, `marker-selection` & `blocked-path`, `marker-count` & `leg-lengths`, `marker-count` & `arm-first-axis`, `marker-count` & `corners`, `marker-count` & `step-form`, `blocked-path` & `leg-lengths`, `blocked-path` & `arm-first-axis`, `blocked-path` & `corners`, `blocked-path` & `step-form`, `edge` & each other point: the two branches' changes applied together
- `step-form` & `leg-lengths`, `step-form` & `arm-first-axis`: the model of `$StoredStep` alone. A stored step has no legs and no first axis. So both points exist only with the concept branch of `step-form`, and they stand at the concept.
- `step-form` & `corners`: each corner of `corners` gets an arm that repeats the stored step turned by the rotation that takes the step's own corner to that corner
- `marker-count` & `blocked-path`: the model of `$SingleMarker` alone. With one non-background cell, no arm reaches a non-background cell.

## Open parameters
- none

## Not formed
- A derived `path_color`: the inputs hold only `background` and the marker, so no cell gives the color 5.
- A derived `diag_axis` or `leg`: a single cell has no orientation and no length to read them from.
- A closed-form test of each cell's offset from the marker in place of the step walk: it gives the concept's output on every input, so it is the concept's model.

## Tickets filed
- 10-640_task_d06dbe63_analyze.md
- 10-641_task_d06dbe63_analyze.md
