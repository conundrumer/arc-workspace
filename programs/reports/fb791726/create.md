# fb791726

## Departures
- The `bridge-frame` point is flattened. `$PerCopy` is the non-concept branch of `Alignment` itself, with no `$BridgeAcrossColumns` constructor, and in the witness file the name `$BridgeAcrossColumns & $PerCopy` became `$PerCopy`: `$BridgeAcrossColumns` with bridged rows found on the canvas fails Fit at test0 and has no case. So the nested type held a concept branch with no case, and the audit rejected `bridge-unaligned-marks` as a witness of `$BridgeAcrossColumns`. For that reason `witness --file programs/reports/fb791726/witnesses.json` reports that `$BridgeAcrossColumns & $PerCopy` denotes no case. Every output it gives matches `witnesses.json`.
- `copy_diag` is stored as the `DiagAxis` `DAXIS_DG`, not as a corner: the audit's relabeling check found that `DIAG_TL` and `DIAG_BR` give the same output. The `Diagonal` instance takes both corners of that axis through `diag_axis_of`.
- `$PerCopy` & `$BridgeAnyGap` & `$BridgeBothAxes` is left out of `impl_choice`: it fails Fit at train0. Marks in columns 1 and 4 are consecutive marked columns, so columns 2–3 get lines.

## Judgments
- Concept pairing reads the concept file literally: two marks of one line `pair_gap` apart bridge every cell strictly between them, whatever those cells hold (`between` + `jump`). `$BridgeAnyGap` adds the condition that no marked cell lies between them (`interrupted`, a defect negation). A first draft used `Ray` stops. That draft required background between the marks, so under `$PerCopy` it drew no line on `line-crosses-mark`, which contradicted `witnesses.json`. It was replaced.
- `$PerCopy` is encoded by its marked set alone: every cell of a line across the pair axis that holds a mark. The pairing clauses are shared with `$SameColumn`.
- `bg=DominantColor` is held as `@derive DominantColor: variant derived`, with `@relaxed square-field`. Its witness (train0 with 0 and 1 swapped) is a color-permuted variant input. The generator would give it a field of 1 with lines, which is the derived output. For this reason the `square-field` scene line is kept in the header.
- `pair_gap=SepTileCount` and `pair_gap=TileCount` fit and get `@ignore: derive`, for failing Relational form. Each reads the gap off a tiling of the input that the task does not have, so its claim refers to a number that counts nothing the task has. The `@ignore: derive` text names Fit, Equivalence and Subsumption only, so whether Relational form is a valid reason there is a judgment.
- The `store` command proposed `@store` lines on `bridged[a]` (AXIS_V) and on a former `span[d, k]`. `bridged` gets `@ignore: store`, under Redundant value: in every variant task the stored axis equals `pair_axis`, so the stored branch adds no parameter. `span` no longer exists.
- Determination: `pair_gap` is derived in `Determine`, from the distance along `pair_axis` from each mark to the next mark of its line, which is a `Ray<Example>` stop. The plan's ScaleRatio covered it only by coincidence. The plan lists bg (DominantColor), copy_count (ScaleRatio), line_color (AnyOutNewColor), copy_diag and pair_axis (enumerable fits) as covered. Each of these proposers reads the fact the concept rests on, so no relation was written for them.
- Deletions judged: the `impl_choice` disjuncts, `between.d`, `same_line(A, P, M1)`, the `axis_of` in `interrupted`, the `$LineKeepsMarks` branches and `copies.diagonal` in `line` stay. Each states a part of a claim that the pairs do not exercise. `nearer(D, M2, M1)` follows from the two other `nearer` atoms, and `ray.cell` in `Determine` is not read by `stop`, so both were removed. Those two removals came after the one `deletions` run, which the doc allows once.
- Final pairs run: every pair passes for all 8 witnessed cases, and lint is ok. The audit, run after the witness file was complete and before the simplify edits, gave no findings.

## Unsettled
- `deletions` was not re-run after the last two atom removals: a second run would settle that they leave nothing else redundant.

## Concept faults
- none

## Fixes elsewhere
- programs/reports/fb791726/analyze.md, the `pair-alignment` entry: it nests `$PerCopy` under `$BridgeAcrossColumns`, whose own model fails Fit. It needs `$PerCopy` given as the across-columns branch directly, so that no branch without a case holds a witness.

## Tickets filed
- none
