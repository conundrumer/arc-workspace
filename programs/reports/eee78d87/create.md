# eee78d87

## Departures
- `$WindowOffsetStored` stores `window_corner(d: DiagDir, p: Position)`, one fact per window corner, in place of analyze.md's `window_offset` (5,5). The witness `off-center-window` reassigns `window_corner` to the four corners of rows 2–7, cols 2–7. It rests on equivariance: an offset from the top-left corner is a hidden orientation, and the determination reads all four corners of the window-color box with no literal corner. Running `witness --file witnesses.json` still reports the `window_offset` key for this reason.
- The `stencil-tiling` phase is written as the tile start that makes the tiling read the same from both edges of each axis (`asymmetric`, `phase`). Each copy must have a center cell and must hold the whole stencil. This matches analyze.md's "2r ≡ canvas − 1 (mod e)" on every odd extent.
- `window_size=ConstInDim` has no case. `derive` reports `window_size=TileCount` as a fit, but analyze.md says it fails Fit. On each input, TileCount's values include the input extent, and the centered windows nest. So wherever ConstInDim is defined, its output is TileCount's output, and ConstInDim fails Subsumption (`@ignore: derive ConstInDim`). The `window_size=TileCount` witness, which is the 8×8 field that `derive` built, stands in place of the `window_size=ConstInDim` witness. I removed that witness because it repeats the same input.
- `field_color=stored` has no case, and I removed its witness. `store` printed no line to add for `field_color`, only `@ignore`. So the relation is marked `@workaround`.
- On a non-square shape box, the solver is undefined because `period` takes two values. An even-extent box is undefined because it has no `tile_center`. A stencil larger than the stored period is undefined through `cut_stencil`. These cases match analyze.md's undefined cases.

## Judgments
- The concept rule `stencil-tiling`, the copies laid symmetric about the canvas center, has a relational form: the tile line is read from each edge with `jump`, `dist` and `stride`, and the start is the one that has no asymmetric line. Nothing is approximated.
- Centered window: this is the box of a canvas cell's images under the two axis flips (`mirror_box`), kept where its extent on each axis is the window extent. This avoids the arithmetic (canvas − window)/2.
- `$WindowTwoStencils`: the window extent is the box of the copies that hold a cell beside the canvas center line on each axis. On the 5×5 X witness this box is 10×10, which matches witnesses.json.
- `$LatticeElements`: the lattice element of a stencil cell is its orbit under `params.element_sym` (SYM_BOX). This is the center alone, a side pair, or the four corners. It is undefined unless the stencil center touches each box edge (`wide_stencil`), which is analyze.md's "undefined off a 3×3 stencil".
- `$CanvasGrowsByMargin` stores `canvas_margin` 5 per side, and its extent is `box_extent` of `uniform_outset`. `$CanvasPerInputCell` is `concat_2d` of an input cell and a stencil cell, cropped by the stencil center's distance to the box edge.
- `window_size=TileCount` (witness `window_size=TileCount`, the 8×8 field): plausibility `variant`, because it breaks `field` (every input is 6×6). Verdict `concept`, because every output keeps the 6×6 window.
- `element_sym`: the plan reports that SYM_1, SYM_LR, SYM_TB and SYM_HT also fit the pairs, because every train shape is symmetric under both flips. It is not an open parameter: a reader of the lattice reading takes a side run as two cells and a block as four, which is SYM_BOX.
- Hint `case section` on `canvas`: kept with `@ignore`. `mirror_box` is keyed by canvas cell and reads every canvas, and each case's window reads only the boxes of its own canvas's cells.
- Deletions: these deletions change no pair, and each one stays. The guards `cut_stencil`, `wide_stencil` and `tile_center(_)` act only off the pairs. The `P2 = P` disjunct serves an odd canvas. The `*_missing` determination checks act where examples disagree.

## Unsettled
- `field_color=stored` (analyze.md's `field-color` branch): `store` gives no `@store` line for a color relation. A runner form for a stored color branch would settle it.
- `element_sym`: the determination-plan entry still stands after 3 runs ("write a determination relation"). No fact of the evidence separates SYM_BOX from its subgroups.
- `$WindowTwoStencils & $WindowOffsetStored`: with four stored corners and an extent other than the stored window's extent, the windows from the four corners are joined. Whether that combination should read one corner is open.
- `mirror_box.cell(C, C)` repeats a cell that the two flip images already bound. I left it, because deletions had already run after the last edit.

## Concept faults
- none

## Fixes elsewhere
- programs/reports/eee78d87/analyze.md, `window_size=<Proposer>` line: TileCount fits every pair by `derive`, and analyze.md says it fails Fit at train0.

## Tickets filed
- none
