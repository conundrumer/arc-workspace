# e6de6e8f

## Departures
- The branch `piece_segment=derived` is the constructor `$DerivedSegments`, and its concept branch `segment-length` is `$GlyphExtent`. In the witness file, every `piece_segment=derived` is now `$DerivedSegments`: the Write step gives a branch named in a form other than a constructor name a constructor of the creator's own naming.
- The witness `background=RarestColor` is now `bg=RarestColor`, with the same input, plausibility and verdict (`variant concept`). The solver's parameter is `bg`, and a `@derive` branch's witness takes the branch's name as its id. The witness that `derive` recorded for that branch (train0 with 0 and 1 swapped) was removed as a duplicate.
- The `piece_segment` assign of `tall-strip`, `diagonal-contact` and `gapped-column` is rewritten as facts of three relations: `piece_glyph` (a glyph mask in its own frame), `piece_paint` and `piece_exit` (Offsets from the piece's start, in grid orientation, stored by GRID_STAMP). The `out_dims` assign of `wide-frame` is rewritten as `[["AXIS_V", 8], ["AXIS_H", 9]]`. `witness --file programs/reports/e6de6e8f/witnesses.json` therefore reports the old names and assign keys as unknown, and it reports `wide-frame` groups as differing, because the solver cannot read the `[[8, 9]]` form. Those are the only differences it prints.
- `source_col` is stored as `source_at(DIR_L, 3)`, a distance from an edge across the flow, so that the program reads no column index.
- `$DerivedSegments & $ColumnRuns` is excluded: where it is defined, each column run is one 4-component and one 8-component, so `$DerivedSegments & $ComponentPieces` and `$DerivedSegments & $Components8` give its output and are defined on more inputs; it fails Subsumption.

## Judgments
- Each piece's start is one step along the flow from the source, then the exits of the pieces before it in read order, added up with no bound: `exit_steps` (an `AxisFrame`) lays out each exit's steps toward each edge, `pen_steps` (a `Tally`) counts the steps of the pieces before each piece, and `pen` composes the four counts as offsets. No `@workaround` remains.
- `$HeightFromInput` builds the scaled extent with `concat` of the input's lines and a `height_ratio` AxisFrame. `$HeightFromInputDiff` and `$WidthFromInputDiff` use `edge_outset`/`edge_inset` with `box_extent`. `$WidthFromSteps` widens a one-line-wide frame by the tallied sideways run on each side with `axis_outset`. None of these uses arithmetic.
- `$HeightFromPipe` reads the pen's position after the last piece. With no piece, the pen stands at the first start, so the `pipe_color=DominantColor` witness gives the one-row frame that `witnesses.json` gives.
- Hints: the `common-subexpr` hints on `next`/`last` in Parse and on `fixed_last`/`fixed_index` are kept with `@ignore`, because each pair reads one edge for two different relations. The ones on `wide`/`ell_defect`/`ell` were resolved by factoring `read_edge`. The `const-join` hint on `params.read_from` and `params.flow_dir` went away with that factoring. Those two parameters are independent, and no Params relation should merge them.
- `@derive` lines: `bg` RarestColor `variant concept` and `pipe_color` DominantColor `variant derived` with `@relaxed pieces-in-a-strip`, both as `analyze.md` gives them. `store` reported no value to add: `frame.extent` equals the stored `out_dims`.
- `deletions`: the 26 deletions that change nothing remove structure that the pairs never instantiate, such as undefinedness on unmatched glyphs (`broken`), L/bar tests on blank cells, the no-piece pen end and the zero-step tally domain, or orientation atoms that a single-orientation task does not exercise. All of them are kept.
- `source_at`: the sweep and the determination admit `(DIR_R, 3)` beside `(DIR_L, 3)`, the same cell of a 7-wide frame. `analyze.md` lists no open parameter, so only `(DIR_L, 3)` is stored.

## Unsettled
- `witness`/`audit` report case pairs that no witness separates or shows differing: `$ComponentPieces` vs `$Components8` under `bg=RarestColor` and under `$TableSegments & bg=stored`, `$ColumnRuns` vs `$Components8` and vs `$ComponentPieces` under several height/width/segment branches, and `$TableSegments` vs `$DerivedSegments & $GlyphExtent` under `$WidthFromInputDiff`, `$WidthFromSteps` and `$Components8`. A witness per combination would settle each pair, for example a diagonal-contact input whose 2 cells outnumber its 0 cells. Otherwise the combination fails Equivalence or Subsumption. The pass ran out of time before building them.
- Determination: the `Determine` comp gives `flow_dir` and `source_at`. `source_at` measures the distance from the edge `params.read_from` names, so it gives the one stored row `(DIR_L, 3)`, not also `(DIR_R, 3)`. The Parse comp is folded into the program, so no `parse unshared with determine` finding remains. The entries for `read_from`, `height_gap`, `width_gap` and `run_length`, and the `piece_glyph`/`piece_paint`/`piece_exit` table, have no determination relation. A determination that replays the walk over each train output, as 136b0064's does, would settle the table and `read_from`.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
