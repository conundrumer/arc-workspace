# db118e2a

## Concept
- The concept fits every pair, train and test, at its stored assignment (`probe.py pairs`).
- Every claim of the concept has a relational form: a bounding box, a 1-cell ring and placement by edge distance. No rule is an approximation.
- No witness has the verdict `other`.

## Choice points
- `canvas-extent`: how the canvas size is set
    - `concept`: the canvas size is the stored `canvas_size`, 15 × 15
    - `$FitCanvas`: replaces `two-copies`. The canvas extent on each axis is derived as `corner_inset` + copy + `copy_gap` + copy + `corner_inset`, where `copy_gap` is 1, and the copies sit at the two ends of `copy_axis`, `corner_inset` from the corner. It reads `bg`, `corner_inset`, `copy_gap` and `copy_axis`, and no `canvas_size`. It is defined on every input on which the concept can cut a picture. It fits every pair.
        - witness `smaller-picture`: breaks `content-extent`, at the stored assignment, plausibility `variant`, verdict `concept`. It breaks the invariant that every input's picture is 3 × 3.
    - `canvas_size=ConstOutDim`: the canvas size is the output size that is the same in every pair. It fails Fit at train0: on that pair's input alone, with `ex_out` empty, it gives no size.
    - `copy-places`: where the two copies go on a stored canvas. This point exists only under the branches that read `canvas_size`, and of those, only `concept` has cases.
        - `concept`: each copy is `corner_inset` cells in from both edges of a corner of `copy_axis`
        - `$CenterGap`: replaces `two-copies`. The copies sit on either side of the canvas center line across `copy_axis`, with one line between them. It reads `canvas_size` and `copy_axis`, and no `corner_inset`. It is undefined where a copy leaves the canvas, or where a canvas extent is even. It fits every pair.
            - witness `smaller-picture`: breaks `content-extent`, at the stored assignment, plausibility `variant`, verdict `concept`. It breaks the invariant that every input's picture is 3 × 3.
        - `$FixedAnchors`: replaces `two-copies`. The top-left cells of the copies are the stored anchors (2,2) and (8,8). It reads `canvas_size` and `copy_anchors`. It is undefined where a copy leaves the canvas or where the two copies paint one cell with two colors. It fits every pair.
            - witness `smaller-picture`: breaks `content-extent`, at the stored assignment, plausibility `variant`, verdict `concept`. It breaks the invariant that every input's picture is 3 × 3.
        - `$ChainFromCorner`: replaces `two-copies`. The first copy is `corner_inset` in from the first corner of `copy_axis`. The second copy follows it along the diagonal with `copy_gap` (1) cells between them. It reads `canvas_size`, `corner_inset`, `copy_gap` and `copy_axis`. It is undefined where a copy leaves the canvas. It fits every pair.
            - witness `smaller-picture`: breaks `content-extent`, at the stored assignment, plausibility `variant`, verdict `concept`. It breaks the invariant that every input's picture is 3 × 3.
- `background`: where the background color comes from
    - `concept`: the stored `bg`, 7
    - `$BgFromCorner`: replaces `bg` in `framed-panel`, `crop-content`, `snug-frame` and `two-copies`. The background is derived as the color of the input's four corner cells. It is undefined where those cells disagree. It fits every pair.
        - witness `recolored-field`: breaks `framed-panel`, at the stored assignment, plausibility `variant`, verdict `$BgFromCorner`. It breaks the invariant that every input's field and corners are 7.
    - `bg=SharedColor`: fails Fit at train0. On that input alone, it gives 7, 4, 9 and 1.
    - `bg=DominantColor`: fails Fit at train2. On that input alone, it gives 7 and 6, which tie at 18 cells. On the test input, it gives 8.
- `frame-width`: how thick the frame is
    - `concept`: the stored `frame_width`, 1, which both cuts the interior and draws the copy frames
    - `$ReadFrameWidth`: replaces `frame_width` in `framed-panel` and `snug-frame`. The width is derived as the number of full rings of the frame color in from the grid edge, with the grid corners left out of each ring. The copy frames are drawn at that width. It is undefined where the edge ring is not of one color. It fits every pair.
        - witness `thick-frame`: breaks `framed-panel` and `content-extent`, at the stored assignment, plausibility `variant`, verdict `$ReadFrameWidth`. It breaks the invariants that every input's frame is 1 cell thick and that every input's picture is 3 × 3. On it, the concept takes the inner ring as marks, so its 9 × 9 copies overlap with conflicting colors and the concept is undefined.
- `picture`: which cells make the picture
    - `concept`: the bounding box of every non-`bg` cell inside the frame
    - `$MarksNotFrameColor`: replaces `crop-content`. The bounding box covers only marks that are not of the frame color. It fails Fit at train1, where every mark is 9, the frame color. It also fails at test0.
    - `$CornerWindow`: replaces `crop-content`. The picture is a stored-size window at a stored corner of the interior. It fails Fit at train1: the picture there is rows 2–4, cols 2–4 of a 7 × 7 interior, and it touches no corner of that interior.
- `copy-corners`: the four corner cells of each copy
    - `concept`: `bg`
    - `$SquareCorners`: replaces `snug-frame`. The copy corners are of the frame color. It fails Fit at train0, train0 output (2,2).
- `canvas-extent` & `background`, `canvas-extent` & `frame-width`, `copy-places` & `background`, `copy-places` & `frame-width`, `background` & `frame-width`: the two branches' changes applied together. Each other pair of points holds a branch that fails Fit, so no case takes a non-concept branch at both.

## Open parameters
- none

## Not formed
- The frame color as a stored parameter: the frame color is 4, 9, 6 and 8 in the four inputs, so no stored value fits. The concept reads it from the input's edge.
- A derivation of `corner_inset`, `copy_gap`, `copy_axis` or `frame_width` by a proposer: no proposer in `programs/proposers.dl` gives an inset, a gap, a diagonal axis or a ring width.
- Copies at all four corners, or at the two corners of the other diagonal: each output shows copies at the top-left and the bottom-right only, and a mirrored variant task changes `copy_axis`, not the program.

## Tickets filed
- none
