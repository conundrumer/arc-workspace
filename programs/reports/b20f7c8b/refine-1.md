# b20f7c8b

## Departures
- `$KindByFrame` has no constructor and no clauses, and the witness `solid-frame-color-box` is not in the witness file (create): the case fails Subsumption. A scratch copy of the solver had a `BoxKind` field with `$KindByFrame` restored and left out of `impl_choice`. `witness <copy> --every-case --witness-file work/task/b20f7c8b/witnesses.json` printed "dropped case `$KindByFrame` fails Subsumption against `concept`". Where `$KindByFrame` is defined, each box takes the same kind under both readings.
- The `legend-source` point has no type (create): `$StoredLegend` fails Fit, so only the concept branch is left. `glyph-parse` (`GlyphParse`) and `panel_color` (`PanelSource`) are fields of `Choice` directly.
- The branches the Analyze file names `concept` are named `$ColorGlyph`, `$StoredPanel`, `$AnyPose` and `$StoredBoxColors`, and `board_color=stored` for the stored board color (create): a constructor cannot be named `concept`.
- `$PanelColorRead` reads all four edge lines of the grid, where the Analyze probe reads only the left and right columns (create): the probe's reading fixes an orientation that the task does not distinguish. The two readings give the same outputs on every pair and on every Analyze witness grid.
- The strip is the lines along either axis that hold a `panel_color` cell and no `board_color` cell, where the Analyze probe takes the bounding box of the `panel_color` cells (create): `witness --file work/task/b20f7c8b/witnesses.json` prints no difference, apart from the `$KindByFrame` name on each witness.

## Judgments
- The departures of create.md hold under the current docs: each rests on a fact the runs confirm, and the one dropped case fails a case condition in an `--every-case` run.
- Checks: the run passes every pair (6 witnessed cases), lint and determination are ok, and the audit reports witness, dropped cases, derive, store and open values ok. Nothing to change.
- Deletions: the 10 deletions that change nothing are the ones create.md judged, together with `colors(Bc, Ps, _, _)` in the `out` clause for cells off the boxes. That atom stays: it makes a `$BoxColorsRead` case undefined where no frame and ink colors are read.
- Simplify and Prune: no change. The code has no lib reimplementation or needless indirection, and the header and comments serve a reader of the solver.
- No `exact_group` parameter for `$ExactFirst` (create): a second `KeyedSetCompare` (`plain`) compares the ink with the glyph untransformed. "Untransformed" is part of that branch's definition and is not task data.
- Keywords `objects match congruent stamp` (create): boxes are components, boxes pair off with legend glyphs by shape up to D4, and a solid box takes its glyph as a footprint. `lookup` does not fit, because the legend is in the input.
- Boxes are the 4-connected components of the cells off the strip and off the board, and the program does not test that a box is 5 × 5. The interior is the cells strictly inside the box's bounding box (create).
- `@derive DominantColor` on `board_color`: `variant derived`, `@relaxed legend-strip` (create). `derive` lists no other fitting derivation, and `store` prints no line to add.
- Not formed items: `match_group` narrower than `SYM_D4`, and a stored D4 transform for the solid-to-glyph draw, fail Fit and get no case (create).
- Determination: `frame_color` is the color on one side of every recolored cell next to a kept cell, and `ink_color` the other color that, with the frame color, is on one side of every recolored cell (create).
- Hints: `single-consumer` on `box_border` and `glyph_box`, both inlined (create).

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- none
