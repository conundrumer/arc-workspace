# c92b942c

## Departures
- The witness file's groups are in the form `record --all` gives (`$CornerOverLine`, `$MarkKept`, `$CornerOverLine & $MarkKept & background=stored`), in place of the Analyze file's `concept` groups: in the witness file, `concept` denotes the concept base, whose cases include `background=DominantColor`, and the first audit failed on the `background=DominantColor` witness for that reason. `witness --file programs/reports/c92b942c/witnesses.json` is ok, so every branch's output equals the Analyze file's.

## Judgments
- Choice: a record `[lc: LineCorner, cm: CornerMark]`. `LineCorner` holds `CornerOverLine` (concept) and `LineOverCorner`. `CornerMark` holds `MarkKept` (concept) and `CornerOverMark`. The concept constructor names are my own. Plus `@derive DominantColor: borderline concept` on `background`, `@relaxed marks-on-background`. The plausibilities and verdicts are those `analyze.md` gives. Every case passes every pair, and there are 4 witnessed cases.
- `$InputFrame` and `$Torus` have no constructor: `analyze.md` gives them no witness, because they fail Fit at train1.
- `derive` lists only `background=DominantColor`. This matches `analyze.md`, where `tile-count=ScaleRatio`, `line-color=OutNewColor`, `diag-color=OutNewColor` and `background=SharedColor` fail Fit. `store` reports no findings, so the solver has no `@store` branch.
- Not formed: I formed no item. Each item is equivalent to the concept, or the pairs separate it, or no source gives it. A color per corner is a payload that does not vary between the corners in any pair, so `diag_color` stays one value.
- The two collision points are encoded as one `shielded(p, ch)` relation. `$MarkKept` shields marks from a corner, and `$LineOverCorner` shields line cells from a corner. `painted` is a corner cell that is not shielded. `out` is one disjunction: corner color, else line color, else the tiled color.
- The off-grid case of `diag-corners` ("a step that leaves the tiled grid paints nothing") holds because `out` ranges over `parse.tiled` alone. So `corner_cell` has no tiled-grid atom: `deletions` reported that atom as one whose removal changes nothing, and the frame of `out` already implies it.
- Other `deletions` findings that I kept: `!shielded` in `painted`, `!painted` in the line branch of `out`, both `shielded` rules, and the two negations in `Determine`. Each one carries a collision claim that the pairs never instantiate, and the witnesses `adjacent-mark-rows` and `diagonal-marks` separate the cases on them.
- Determination: the plan asked for a relation for `line_color` and `diag_color`, which `AnyOutNewColor` derives from a fact the concept does not read. `Determine.line_color` is the output color of a line cell that is no corner. `Determine.diag_color` is the output color of a corner cell that is no mark. The tiled parse moved into `Parse<Key>`, which the program and `Determine` share. I wrote no relation for `background` (DominantColor reads the field color, the fact `marks-on-background` gives), `tile_count` (ScaleRatio reads the output size as copies of the input, the fact `tile` gives) or `line_axis` (fixed by the fit over `Axis`, as in c803e39c). `diag_dirs` is decided by the fit.
- Keywords `tile-arrangement lines markers stamp`. The output arranges copies of the input. Each marked row draws a line. The marks fix where the lines and the corners go. The two corner cells are a fixed footprint at each mark, as in 10fcaaa3.
- Hints: lint gave none. Performance: each run takes 1–3 s.

## Open
- The combinations `$LineOverCorner & $CornerOverMark`, and each branch together with `background=DominantColor`, are not witnessed, so no check runs them. Every verdict on those branches is `concept`, so no witness can witness these combinations.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
