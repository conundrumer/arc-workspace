# b6f77b65

## Concept
- Fits every pair (`check_concept.py` with the arches annotated by hand, and `probe.py` with the arches parsed as the one exact cover of the non-marker cells by arches). Each claim has a relational form: the settle is rigid bodies falling toward one heading (`Gravity` in cells.dl), and a bar's hold is a test on the cells beside its two ends.
- No witness has the verdict `other`.
- After the concept file was written, the probe showed that `bar-hangs` does not always end the bar at the top of the lower leg. On `far-leg-drops-past-near-foot`, no line has a leg cell beside both ends of the bar, so the bar drops to the frame edge. The rule now says that the bar stops at the frame edge as well as at a stick, and the claim about the lower leg's top is gone from it.

## Choice points
- `bodies`: what moves as one body
    - `concept`: each stick, a leg or a bar (`legs-fall`, `bar-hangs`, `bar-drops`)
    - `$ColorBodies`: replaces `legs-fall`, `bar-hangs`, `bar-drops`: each one-color 4-connected part of the sticks left moves toward `fall_dir` until a cell past it is the frame edge or another part; no parameter; defined wherever the concept is. Fails Fit: train1 (the top arch's bar `5 5 5` drops to row 7, and the output holds it at row 5).
    - `$RigidArch`: replaces `legs-fall`, `bar-hangs`: an arch that keeps its bar and both legs moves as one body; an arch that lost a stick splits into sticks as in the concept; no parameter; defined wherever the concept is. Fails Fit: train1 (the arch of `2`, `3`, `3` at rows 6–8 drops 2 as one body, held by its left leg, and the output drops its `3` sticks 3).
- `corner`: which stick the corner cell at a leg's top joins
    - `concept`: its leg (`sticks`)
    - `$CornerWithBar`: replaces `sticks`: a corner cell joins the bar where the bar has its color, and its leg otherwise; no parameter; defined wherever the concept is. Fails Fit: train2 (the bar `5 5` at train2 input (9,2)–(9,3) rests on the leg at col 3 and stays, and the output drops (9,2) to (11,2)).
- `whole-bar`: where the bar of an arch that keeps both legs comes to rest
    - `concept`: `bar-hangs`
    - `$BarAtLowerTop`: replaces `bar-hangs`: the bar moves toward `fall_dir` until it lies on the line of the top of its lower leg, or a cell past it is a stick; no parameter; defined wherever the concept is. Fits every pair. Witness `far-leg-drops-past-near-foot`, at the stored assignment, breaking no scene claim: plausibility `ordinary`, verdict `concept`.
    - `$BarAlwaysDrops`: replaces `bar-hangs` with `bar-drops` for every bar; no parameter; defined wherever the concept is. Fails Fit: train1 (the top arch's bar drops to row 7, and the output holds it at row 5).
- `broken-bar`: where the bar of an arch that lost a leg comes to rest
    - `concept`: `bar-drops`
    - `$BarToFoot`: replaces `bar-drops`: the bar moves toward `fall_dir` until it lies beside the end of the leg it keeps, or a cell past it is the frame edge or a stick; no parameter; defined wherever the concept is. Fits every pair. Witness `broken-bar-overhangs`, at the stored assignment, breaking no scene claim: plausibility `ordinary`, verdict `concept`.
    - `$BarKeepsLeg`: replaces `bar-drops`: the bar and the leg it keeps move as one body; no parameter; defined wherever the concept is. Fails Fit: train1 (the bar `7 7 7 7` at row 9 stays joined to the leg of `1` and does not drop to row 11).
- `marker-colors`: which colors the marker names
    - `concept`: the color of each marker cell (`pull-marked`)
    - `$CornerColorOnly`: replaces `pull-marked`: only the color of the marker cell at `marker_corner` is pulled; no parameter; defined wherever the concept is. Fails Fit: test1 (the marker `2 1` pulls the sticks of `1` too, and this branch keeps them).
- `fall_dir`
    - `concept`: the stored `DIR_B`
    - `$FallToFloorEdge`: replaces the stored `fall_dir` with a value derived on each input: the direction of the frame edge that the most non-background cells touch; undefined on an input where two edges tie for the most. Fits every pair (the bottom edge has 2 to 4 cells, and the top and left edges at most 2). Witness `structure-on-left-edge`, at the stored assignment. At `DIR_B` it breaks `marker` (the marker sits at the top-right corner, and the line next to the top edge is not empty), `arches` and `stacked` (the legs run along rows). Plausibility `variant`, as a turned scene is what a turned variant task contains. Verdict `$FallToFloorEdge`. It breaks this invariant of the inputs: the structure stands on the bottom edge, with the marker at the top-left corner.
- `background`
    - `concept`: the stored `0`
    - `background=DominantColor`: the commonest color of the input; undefined where it is not unique. Fits every pair. Witness `background=DominantColor`, at the stored assignment, breaking no scene claim: plausibility `borderline`, verdict `concept`. It breaks these invariants of the inputs: `0` is the commonest color of every input, and no two legs of different arches lie side by side.
- `whole-bar` & `broken-bar`, `whole-bar` & `fall_dir`, `whole-bar` & `background`, `broken-bar` & `fall_dir`, `broken-bar` & `background`, `fall_dir` & `background`: the two branches' changes applied together
- No case takes a non-concept branch at `bodies`, `corner` or `marker-colors`, since each of those branches fails Fit.

## Open parameters
- none

## Not formed
- The marker cells are cleared with the sticks they name: every output keeps the marker cells, train0's included, so a reader of the pairs does not take this reading.
- Each column's cells pack toward `fall_dir` one cell at a time: the pairs show rigid sticks. In train4 the bar `3 3 3` comes to rest at row 8 above two empty cells of col 4.
- The order in which bodies settle, one at a time or all together: each body moves only toward `fall_dir`, and it stops on what lies past it at rest, so every order reaches the same rest and gives no other model.
- `marker_corner` stored or derived: no rule reads it, because the rules read the marker as the non-background cells of the line on the edge opposite `fall_dir`. No model differs on it.

## Tickets filed
- 10-376_task_b6f77b65_analyze.md
- 10-377_task_b6f77b65_analyze.md
