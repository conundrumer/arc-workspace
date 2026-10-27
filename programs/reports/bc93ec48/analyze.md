# bc93ec48

## Concept
- The concept fits every pair (probe `work/task/bc93ec48/probe.py`, reading `concept`).
- No witness has the verdict `other`. Every rule has a relational form, so the concept rule is applied as written.

## Choice points
- `shape-cells`: which cells make up one shape
    - `concept`: a 4-connected one-color component of non-`background` cells
    - `$Conn8`: replaces `corner-shape` with an 8-connected one-color component; no new parameters; defined wherever the concept is. Fits every pair. Witness `diagonal-touch`: plausibility `ordinary`, verdict `concept`. It breaks no scene claim, and test0's input has 8 at (2,15) that touches the 8 block at (3,14) only at a corner.
    - `$MultiColor`: replaces `corner-shape` with a 4-connected component of non-`background` cells of any colors, each cell keeping its color in the copy. Fails train0, because the 8 at (2,8) and the 9 shape beside it join the TR 6 shape and move with it.
    - `$ColorClass`: replaces `corner-shape` with every cell of the corner cell's color. Fails train0, because the 9 class includes the shape at (0,6)–(2,7).
- `corner-pick`: which shape a corner holds
    - `concept`: the shape that holds the corner cell
    - `$EdgePair`: replaces `corner-shape` with the shape that reaches both edges through the corner; undefined where two shapes do. Fits every pair. Witness `shape-hugs-empty-corner`: plausibility `borderline`, verdict `$EdgePair`. It breaks this invariant of the inputs: each shape that reaches both edges at a corner holds the corner cell.
- `copy-form`: how the shape is laid down at the next corner
    - `concept`: translated, with its bounding box touching the target corner's two edges
    - `$Turn`: replaces `next-corner` with the shape turned by the rotation that takes its corner to the target corner, then placed the same way. Fails train0, because the 6 shape lands turned at BR.
    - `$Mirror`: replaces `next-corner` with the shape reflected across the axis between its corner and the target corner, then placed the same way. Fails train0, because the 6 shape lands flipped top to bottom at BR.
    - `$CornerAnchor`: replaces `next-corner` with a translation that takes the corner cell onto the target corner cell; undefined where the copy leaves the grid. Fails train0, because the TR 6 shape leaves the grid.
- `vacated-cells`: what the cells of a shape that moved away become
    - `concept`: they keep their input color unless a copy covers them
    - `$Erase`: replaces `overlay` with those cells turning `background` before the copies are drawn. Fails train0, because (0,1) and (1,1) stay 4.
- `draw-layer`: whether a copy covers non-background cells
    - `concept`: a copy is drawn over every cell it covers
    - `$Underlay`: replaces `overlay` with a copy that paints only `background` cells. Fails train0, because (0,8) turns from 6 to 4.
- `corner-step`: how the target corner of each corner is encoded
    - `concept`: the next corner in `sense`, a stored `Sense`
    - `$CornerD4`: replaces `sense` with a stored `D4` element `corner_d4` (`D4_CW`) whose action on the corners gives each target. Fits every pair. Witness `corners-swap`, at `corner_d4` = `D4_LR` and `corner_target` = the left-right swap: plausibility `ordinary`, verdict `$CornerMap`. It fails Subsumption, because each `corner_d4` value gives on every input the output of `$CornerMap` at the action of that value on the corners.
    - `$CornerMap`: replaces `sense` with a stored target corner per corner, `corner_target` (TL→TR, TR→BR, BR→BL, BL→TL). Fits every pair. Witness `corners-swap`: plausibility `ordinary`, verdict `$CornerMap`.
- `background`: the field color
    - `concept`: stored, 7
    - `background=DominantColor`: the commonest color of the input, in place of the stored `background`. Fits every pair. Witness `background=DominantColor`: breaks `background-field`, plausibility `variant`, verdict `background=DominantColor`. It breaks this invariant of the inputs: 7 is the field color.
    - `background=SharedColor`: every color of the input. Fails train0, because each color other than 7 makes the 7 field a corner shape whose copies clash, so the model is undefined.
    - `background=RarestColor`: the rarest color of the input. Fails train0, because the 2 shape at BL becomes background and TL does not get its copy.
- `shape-cells` & `corner-pick`, `shape-cells` & `copy-form`, `shape-cells` & `vacated-cells`, `shape-cells` & `draw-layer`, `shape-cells` & `corner-step`, `shape-cells` & `background`, `corner-pick` & `copy-form`, `corner-pick` & `vacated-cells`, `corner-pick` & `draw-layer`, `corner-pick` & `corner-step`, `corner-pick` & `background`, `copy-form` & `vacated-cells`, `copy-form` & `draw-layer`, `copy-form` & `corner-step`, `copy-form` & `background`, `vacated-cells` & `draw-layer`, `vacated-cells` & `corner-step`, `vacated-cells` & `background`, `draw-layer` & `corner-step`, `draw-layer` & `background`, `corner-step` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- the counterclockwise `sense`: it is a value of `sense`, not a branch, and it fails train0.
- `sense` derived: no proposer in `programs/proposers.dl` gives a `Sense` or a corner map.
- `background` by `OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`, `ChangedPairs`, `VanishedNewPairs`: these read `ex_out`, which is empty in a run on one input, so they give no field color.
- `background` by `CountRankAsc` or `CountRankDesc`: these give a rank per color, not one color. Rank 0 of `CountRankDesc` is the `DominantColor` branch.

## Tickets filed
- none
