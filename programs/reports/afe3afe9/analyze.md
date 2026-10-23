# afe3afe9

## Concept
- Fits every pair (train0–2, test0). No witness has the verdict `other`.
- The verdict goes to a branch over the concept at these witnesses:
    - `band-opposite-turn` (`variant`): `$PackTowardUniformHalf` and `$PackTowardColorHalf`.
    - `line_color=RarestColor` and `bg_color=DominantColor` (`variant`): the derived colors.
    - `filled-square`, `first-cross-line-empty` and `pack-line-empty` (`borderline`): `$ComponentUnit`, `$FrameTiling` and `$StoredAlongExtent`.
- In every pair, the band of one color (8) lies a quarter turn clockwise from the line. So the stored `turn_sense` and a half that the input marks always give the same pack side.
- On the pack axis, the middle slot line is empty in every input (`pack-gap-empty`). Every slot line across the pack axis holds a square. So in all pairs the output is 7 lines of 6 cells under each reading of the extent.

## Choice points
- `pack-side`
    - `concept`: the pack side is the line's side turned a quarter turn in `turn_sense` (clockwise).
        - `line_color`
            - `concept`: stored, 1.
            - `line_color=RarestColor`: replaces the stored `line_color` with the rarest color of the input (`RarestColor`). Undefined where two colors tie for rarest, or where that color forms no single full edge line. Fits every pair. Witness `line_color=RarestColor`: train0 with the line recolored 5. It breaks `edge-line`, stands at the stored assignment, and has plausibility `variant` and verdict `line_color=RarestColor`. It breaks the input invariant that the line is color 1.
            - `line_color=SharedColor`: replaces the stored `line_color` with every color the input holds. Fails Fit at train0: row 0 (color 1) and row 29 (color 0) are both full edge lines, so there are two line sides.
    - `$PackTowardUniformHalf`: replaces `pack-side`. On each axis, the middle slot line of the squares' span cuts the tiling into two halves. The pack side is the side of the only half whose squares share one color. It reads neither the line nor `turn_sense`. Undefined where an axis spans an even number of slot lines, or where the one-colored halves are not exactly one. Fits every pair.
        - Witness `band-opposite-turn`: train0 mirrored left to right, so the line stays on top and the 8 band lies on the left. It breaks no scene claim, stands at the stored assignment, and has plausibility `variant` and verdict `$PackTowardUniformHalf`. It breaks the input invariant that the one-colored half lies a quarter turn clockwise from the line.
        - `quadrants-one-color` (train0 with color 3 made 2; `ordinary`, verdict `concept`) shows the branch undefined where the concept and `$PackTowardColorHalf` are defined.
    - `$PackTowardColorHalf`: replaces `pack-side`. The pack side is the side of the only half whose squares are all `band_color` (8). It reads neither the line nor `turn_sense`. Undefined where an axis spans an even number of slot lines, or where such halves are not exactly one. Fits every pair.
        - Witness `band-opposite-turn`, as for `$PackTowardUniformHalf`, with plausibility `variant` and verdict `$PackTowardUniformHalf`. Both branches are in that group.
        - `band-recolored` (train0 with color 8 made 5; `variant`, verdict `concept`) shows the branch undefined where the concept and `$PackTowardUniformHalf` are defined.
    - `$PackTowardFullerHalf`: replaces `pack-side`. The pack side is the side of the half that holds the most squares. Fails Fit at test0: the top, bottom and left halves tie at 13 squares.
    - `$RotatedOutput`: replaces `pack-side` and `output-extent`. Each line packs toward the line's side, and then the output turns a quarter turn in `turn_sense`. Fails Fit at train0: output row 0 is `2 2 2 8 8 8`, and this branch's row 0 holds the squares of the slot column at input cols 1–3 read from the bottom, `3 2 2`.
- `unit`
    - `concept`: a hollow square of side `ring_side` with a background center is one cell.
    - `$ComponentUnit`: replaces `ring-cell`. Each 4-connected piece of non-background cells that fits in a `ring_side` box is one cell, at the slot of its box. Undefined where a piece holds two colors, or where the pieces are off one tiling. Fits every pair. Witness `filled-square`: train0 with cell (3,2) set to 2, so one square is solid. It breaks `ring-tiling`, stands at the stored assignment, and has plausibility `borderline` and verdict `$ComponentUnit`. It breaks the input invariant that every square is hollow.
- `cross-lines`
    - `concept`: one output line per slot line across the pack axis, from the first line that holds a square to the last.
    - `$RankedLines`: replaces the part of `output-extent` that is across the pack axis. There is one output line per slot line that holds a square, and empty lines drop. Fits every pair. Witness `middle-cross-line-empty`: train0 with rows 14–16 cleared. It breaks no scene claim, stands at the stored assignment, and has plausibility `ordinary` and verdict `concept`.
    - `$FrameTiling`: replaces the part of `output-extent` that is across the pack axis. There is one output line per slot line whose slot fits inside the frame. Fits every pair. Witness `first-cross-line-empty`: train0 with rows 2–4 cleared. It breaks `ring-tiling` (the squares span 6 rows), stands at the stored assignment, and has plausibility `borderline` and verdict `$FrameTiling`. It breaks the input invariant that the first and the last slot lines across the pack axis each hold a square.
- `along-extent`
    - `concept`: the output holds one cell per slot line on the pack axis that holds a square.
    - `$MostRingsExtent`: replaces the part of `output-extent` that is along the pack axis. The output is as long as the most squares that any line holds. Fits every pair. Witness `no-full-line`: train0 with the squares at rows 2–4 and rows 18–20, cols 1–3, cleared. It breaks no scene claim, stands at the stored assignment, and has plausibility `ordinary` and verdict `concept`.
    - `$StoredAlongExtent`: replaces the part of `output-extent` that is along the pack axis with a stored length `along_count` (6). Undefined where a line holds more squares than that. Fits every pair. Witness `pack-line-empty`: train0 with cols 5–7 cleared below the line. It breaks no scene claim, stands at the stored assignment, and has plausibility `borderline` and verdict `$StoredAlongExtent`. It breaks the input invariant that every slot line on the pack axis other than the middle one holds a square.
- `line-order`
    - `concept`: the cells keep their order along the line.
    - `$ColorOrderedLine`: replaces `pack-lines`. A stored order of colors sorts the cells of each line. Fails Fit at test0: color 7 is a key that no train pair holds.
    - `$PackPerHalf`: replaces `pack-lines`. Each half of a line packs within its own three slots. Fails Fit at train0: row 1 gives `0 0 2 0 0 8` and the output is `0 0 0 0 2 8`.
- `bg_color`
    - `concept`: stored, 0.
    - `bg_color=DominantColor`: replaces the stored `bg_color` with the commonest color of the input (`DominantColor`). Undefined where two colors tie. Fits every pair. Witness `bg_color=DominantColor`: train0 with color 0 made 5. It breaks `edge-line`, stands at the stored assignment, and has plausibility `variant` and verdict `bg_color=DominantColor`. It breaks the input invariant that the background is 0.
- `pack-side` & `unit`, `pack-side` & `cross-lines`, `pack-side` & `along-extent`, `pack-side` & `line-order`, `pack-side` & `bg_color`, `unit` & `cross-lines`, `unit` & `along-extent`, `unit` & `line-order`, `unit` & `bg_color`, `cross-lines` & `along-extent`, `cross-lines` & `line-order`, `cross-lines` & `bg_color`, `along-extent` & `line-order`, `along-extent` & `bg_color`, `line-order` & `bg_color`, `line_color` & `unit`, `line_color` & `cross-lines`, `line_color` & `along-extent`, `line_color` & `line-order`, `line_color` & `bg_color`: the two branches' changes applied together.
    - The half branches of `pack-side` cut their halves on the tiling of the squares' span, also where `$FrameTiling` gives the output lines across the pack axis.
- `line_color` stands under the concept branch of `pack-side`. The half branches and `$PackTowardFullerHalf` do not read the line, so a case that takes one of them and `line_color=RarestColor` has that `pack-side` branch's model alone.

## Open parameters
- none

## Not formed
- Pack toward the line, or away from it: no turn of the line's side other than a quarter turn fits train0. There, the cells pack along rows and the line is a row. The sense of the quarter turn is the parameter `turn_sense`, and the pairs fix it to clockwise.
- `band_color` derived by `SharedColor` under `$PackTowardColorHalf`: on one input, that derivation gives every color the input holds. Then each one-colored half qualifies, which is the model of `$PackTowardUniformHalf`, so it fails Equivalence.
- Other proposers on `line_color` and `bg_color` (`DominantColor` for the line, `RarestColor` or `SharedColor` for the background): on train0 they give no line, or several background colors, so no square or line side is found.
- Derivations of `ring_side`, `ring_gap` and `turn_sense`: no proposer reads the size of a piece, a gap between pieces, or a sense.
- A stored place of the tiling in the frame: the squares start at row 2 in train0 and at row 1 in train2, so a stored placement fails Fit. `$FrameTiling` derives the place from the squares and the frame.
- Each quadrant slides as one rigid block: train0 shows the 2 quadrant's rows ending at different columns (`2 2 2` at cols 0–2 in row 0, at cols 1–3 in row 2), so the cells move one by one.

## Tickets filed
- none
