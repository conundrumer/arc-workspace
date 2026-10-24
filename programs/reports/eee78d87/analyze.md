# eee78d87

## Concept
- Fits every pair: train0, train1, train2 and test0 (`work/task/eee78d87/check_concept.py`, `work/task/eee78d87/probe.py`).
- No witness has verdict `other`. Every rule has a relational form (a period read off the stencil box, modular placement, and a centered window), so nothing is approximated.
- Undefined where the scene breaks: off-background cells of more than one color, a stencil box that is not square or has even extent (no center cell), or `canvas_size` − `window_size` odd (no centered window).
- The tiling phase is stated as "symmetric about the canvas center" so that the model stays equivariant. At 16 with period 3, that is the edge-anchored phase the pairs show.

## Choice points
- `canvas-extent`
    - `concept`: `canvas_size` stored, 16.
    - `$CanvasPerInputCell`: replaces `canvas`. The canvas is e·`in_size` − (e − 1), one stencil copy per input cell with the outer half-copies cropped. It has no parameter and is undefined on a non-square input. It fits every pair. Witness `wider-field` (8×8 field, plus stencil) at the stored assignment gives 22×22 against the concept's 16×16. It breaks `field` (`in_size`). Plausibility `variant`, breaking the invariant that every input is 6×6. Verdict `concept`.
    - `$CanvasGrowsByMargin`: replaces `canvas`. The canvas is `in_size` + `canvas_margin` (10), undefined on a non-square input. It fits every pair. Witness `wider-field` gives 18×18. It breaks `field` (`in_size`). Plausibility `variant`, breaking the invariant that every input is 6×6. Verdict `concept`.
    - `canvas_size=<Proposer>`, for each proposer: replaces `canvas`. Read from one input alone, ConstInDim, TileDim, TileCount and Period give 6 or less. ConstOutDim, ConstOutDimAxis, DimDiff, ScaleRatio and ScaleRatioAxis read outputs and give nothing, so they are undefined on every input. All fail Fit at train0.
- `window-extent`
    - `concept`: `window_size` stored, 6.
    - `window_size=ConstInDim`: replaces `center-window`'s extent with the input's extent. Undefined where the input dims differ (two values) or where canvas − extent is odd. It fits every pair. Witness `window_size=ConstInDim` (8×8 field) at the stored assignment recolors a centered 8×8 window against the concept's 6×6. It breaks `field` (`in_size`). Plausibility `variant`, breaking the invariant that every input is 6×6. Verdict `concept`.
    - `$WindowTwoStencils`: replaces `center-window`'s extent with 2·period, the two central stencil copies on each axis. It drops `window_size`. It fits every pair. Witness `five-wide-stencil` (a 5×5 X stencil) at the stored assignment recolors a 10×10 window against 6×6. It breaks `one-shape` (`shape_extent`). Plausibility `variant`, breaking the invariant that every shape's box is 3×3. Verdict `concept`.
    - `window_size=Period`: Period gives 5 on train1's input, and 16 − 5 is odd, so no window centers. It fails Fit at train1.
    - `window_size=<Proposer>` for TileDim, TileCount and the proposers that read outputs: several values on a 6-wide input, or none. It fails Fit at train0.
- `window-place`
    - `concept`: the window is centered.
    - `$WindowOffsetStored`: replaces the centering in `center-window`. Parameter `window_offset`, (5,5). Undefined where the window leaves the canvas. It fits every pair. Witness `off-center-window` (train0 input) at the assignment `window_offset` = (2,2) recolors rows 2–7, cols 2–7. It breaks no scene claim. Plausibility `variant`: the input breaks no invariant of the inputs, and the reassignment moves the window, which every output centers. Verdict `$WindowOffsetStored`.
- `tiling-phase`
    - `concept`: copies sit symmetric about the canvas center, with copy centers on rows and cols where 2r ≡ `canvas_size` − 1 (mod period).
    - `$PhaseFromCorner`: replaces the phase in `stencil-tiling`, putting a copy's center on the row and column of a stored canvas corner. It reads the open parameter `anchor_corner`. It fits every pair, since all four corners give one grid at 16. Witness `canvas-off-period` (train0 input) at the assignment `canvas_size` = 18 gives four grids (copy centers 0,3,…,15 or 2,5,…,17 on each axis) against the concept's centers 1,4,…,16. It breaks no scene claim. Plausibility `variant`: no invariant of the inputs breaks, and every output's canvas is 16. Verdict `concept`.
- `stencil-reading`
    - `concept`: each output cell reads one stencil cell, the stencil tiled cell by cell.
    - `$LatticeElements`: replaces `stencil-tiling`'s cell reading. The output is a lattice of 1-wide lines every period. A crossing takes the stencil's center cell. A run between crossings takes the two side cells on its axis. A block takes the four corner cells. A run or block is a hole when any of its stencil cells is held. Undefined off a 3×3 stencil. It fits every pair. Witness `asymmetric-stencil` (an L-shaped stencil) at the stored assignment gives runs and blocks whole where the concept splits them. It breaks no scene claim. Plausibility `variant`, breaking the invariant that every shape is symmetric under both mirror flips. Verdict `concept`.
        - `lattice-combine`
            - `concept`: a run or block is a hole when any of its stencil cells is held.
            - `$LatticeAll`: a run or block is a hole only when all of its stencil cells are held. It fits every pair. Witness `asymmetric-stencil`. Plausibility `variant`, breaking the invariant that every shape is symmetric under both mirror flips. Verdict `concept`.
    - `$StencilLookup`: replaces `stencil-tiling`'s source with a stored table from shape to stencil. It fails Fit at test0, where the four-corner shape is an unseen key.
    - `$StencilByColor`: replaces `stencil-tiling`'s source with a stored table from shape color to stencil. It fails Fit at test0, where color 2 is an unseen key.
- `stencil-polarity`
    - `concept`: the shape's cells are the holes.
    - `$StencilInverted`: the cells the shape leaves empty are the holes. It fails Fit at train0.
- `period`
    - `concept`: the period is the stencil box's extent, derived.
    - `period=stored`: the period is stored (3), and the stencil is centered in each period×period tile with field around it. Undefined where extent > period or period − extent is odd. It fits every pair. Witness `period=stored` (train0 input) at the assignment `period` = 5 gives the plus centered in 5×5 tiles against the concept's period 3. It breaks no scene claim. Plausibility `variant`: no invariant of the inputs breaks, and every output repeats with period 3. Verdict `period=stored`.
- `field-color`
    - `concept`: non-hole cells take the input's background, derived as its commonest color.
    - `field_color=stored`: stored 7. It fits every pair. Witness `field_color=stored` (train0 on a field of 5) at the stored assignment fills with 7 against the concept's 5. It breaks no scene claim. Plausibility `variant`, breaking the invariant that every input's background is 7. Verdict `concept`.
- `hole-color`
    - `concept`: `hole_color` stored, 0.
    - `hole_color=<Proposer>`, for each proposer: on one input, RarestColor gives the shape color, DominantColor gives 7, and SharedColor gives 7 and the shape color. OutNewColor, AnyOutNewColor and the other proposers that read outputs give nothing. All fail Fit at train0.
- `window-color`
    - `concept`: `window_color` stored, 9.
    - `window_color=<Proposer>`, for each proposer: no proposer that reads one input alone gives 9, and those that read outputs give nothing. All fail Fit at train0.
- `canvas-extent`, `window-extent`, `window-place`, `tiling-phase`, `stencil-reading`, `lattice-combine`, `stencil-polarity`, `period`, `field-color`, `hole-color`, `window-color`, each pair of them: the two branches' changes applied together.

## Open parameters
- `anchor_corner`: TL, TR, BL, BR, under `$PhaseFromCorner`

## Not formed
- The stencil box located other than by the shape's bounding box (a fixed frame, or a frame around a marked cell): no input marks a frame, every shape's box is 3×3, and no source of step 1 gives such a frame.
- The window placed by where the shape sits in the input: the shape sits at rows 3–5 in train0, rows 1–3 in train1 and train2, and rows 0–2 in test0, while every output puts the window at rows 5–10, cols 5–10. No pair ties the window to the shape, and no source gives such a placement.
- The shape's color reaching the output: no output holds 3, 1, 6 or 2, so nothing reads it beyond the lookup branch `$StencilByColor`.
- A background read other than as the commonest color (a corner cell, the border's color): no source of step 1 gives one, since DominantColor is the commonest color. The scene puts one shape of at most 9 cells on a field of 36.

## Tickets filed
- none
