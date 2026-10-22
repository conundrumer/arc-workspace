# b20f7c8b

## Departures
- `$KindByFrame` has no constructor and no clauses, and the witness `solid-frame-color-box` is gone from the witness file: the `witness` run showed no input on which `$KindByFrame` is defined and differs from the concept case, so it fails Subsumption. Where it is defined, every box takes the same kind under both readings. The witness separated only that branch.
- The `legend-source` point has no type: `$StoredLegend` fails Fit and has no witness, so only the concept branch is left. `glyph-parse` (`GlyphParse`) and `panel_color` (`PanelSource`) are fields of `Choice` directly, with no type that has one constructor above them.
- The branches the Analyze file names `concept` are named `$ColorGlyph`, `$StoredPanel`, `$AnyPose` and `$StoredBoxColors`. `record --all` rewrote the witness file's groups to those names, and to `board_color=stored` for the stored board color.
- `$PanelColorRead` reads all four edge lines of the grid. The Analyze probe reads only the left and right columns. That probe's reading fixes an orientation that the task does not distinguish. The two readings give the same outputs on every pair and on every Analyze witness grid.
- The strip is found as the lines along either axis that hold a `panel_color` cell and no `board_color` cell. The Analyze probe takes the bounding box of the `panel_color` cells. `witness --file work/task/b20f7c8b/witnesses.json` printed no difference, apart from the `$KindByFrame` name.

## Judgments
- No `exact_group` parameter for `$ExactFirst`: a second `KeyedSetCompare` (`plain`) compares the ink with the glyph untransformed. That branch's "untransformed" is part of its definition and is not task data. The sweep showed that the pairs admit every `Sym` value for such a parameter. With a parameter, a reader would take it as free, and the identity would need a literal.
- Keywords `objects match congruent stamp`: boxes are components; boxes pair off with legend glyphs by shape (`match`), up to D4 (`congruent`); a solid box takes its glyph as a footprint (`stamp`). `lookup` does not fit, because the legend is in the input and is not stored data.
- Boxes are the 4-connected components of the cells that are off the strip and off the board. The program does not test that a box is 5 × 5. The interior is the cells strictly inside the box's bounding box, so the 1-wide frame needs no literal.
- `@derive DominantColor` on `board_color`: `variant derived`, `@relaxed legend-strip`, as the Analyze report gives it. `derive` lists no other fitting derivation, so `panel_color`, `frame_color` and `ink_color` get no proposer branch (Analyze, Not formed).
- `store` prints no `@store` line to add. Each finding is already stored, or stands at a different place on each input.
- Not formed, `match_group` narrower than `SYM_D4`: no case. The sweep reports `SYM_D4` as the one value that fits.
- Not formed, a stored D4 transform for the solid-to-glyph draw: no case. Train1's 3 glyph has no symmetry, so only the identity fits, and that is the concept case.
- Determination: `frame_color` is the color on one side of every recolored cell that is next to a kept cell. `ink_color` is the other color that, with the frame color, is on one side of every recolored cell. The plan covers `board_color` (DominantColor), `match_group` and `panel_color` by enumeration.
- Hints: `single-consumer` on `box_border` and on `glyph_box`. Both relations were inlined into their one use.
- Deletions that change nothing: the box-membership atoms in `ink` and `drawn` (which `crop` and `compose` on the interior box already imply), the `d` column of `matched`, and `impl_choice` in the glyph-box `paint` clause were removed. The others stay because they state a claim that the pairs never test: `same_line` and `!panel` in the strip and legend cells, `params.match_group`, the `color_glyph.value` and `colors` gates that make a case undefined, the `glyph_box` test (now `box_color.clash`), and `$ExactFirst`'s `plain`/`exact` and `exact.col`.
- Witnesses built: none. Every remaining branch has its Analyze witness. `witness` and `audit` report ok.

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- none
