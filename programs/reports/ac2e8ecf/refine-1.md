# ac2e8ecf

## Departures
- (create) The header adds the rule `kind`, which says that a shape that closes off a region by itself, under 4-adjacency, is a rectangle and that every other shape is a cross. The `single-color-objects` scene says "4-connected". The concept file gives the kind test only inside the scene claim `two-kinds`, and the `kind-test` and `shape-parse` choice points each need a claim for their `@claim` to name and for their branches to change. Judged again: it holds.
- (create) `background` has the line `// @derive DominantColor: variant derived`, and `$BackgroundMode` has no constructor. `derive` lists DominantColor as a fitting derivation, and a branch equivalent to a `@derive` branch loses its constructor. The derive witness `background=DominantColor` is train 0 with 0 and 3 swapped, a routine color variant that the generator would pair with the derived branch's output. `dense-box` stays in the witness file as a further witness of that branch. Judged again: it holds. This pass rewrote the `separates` text of `dense-box`, which still named `$BackgroundMode`, to name `background=DominantColor`.
- (create) The contact branch `$StackRectanglesByBbox` makes rectangles stop by their bounding box and crosses by their cells. It is formed from the Not formed item "Bounding-box contact for rectangles alone", whose equivalence argument holds only for rectangle outlines: under the concept kind test, any shape that closes off a region rises. Witness `tailed-box` (a 3x3 outline of 4 with a knob cell) separates it from the concept. It fits every pair. Judged again: it holds.
- (create) No case takes `$Apart` together with a non-concept branch, so `impl_choice` holds the concept case and every case with `$RectanglesOnTop` or `$CrossesOnTop`, and `@ignore: derive concept` stands under the `@derive` line. A case that takes `$Apart` is undefined exactly where a settled rectangle and a settled cross share a cell, and elsewhere it gives the output of the matching `$RectanglesOnTop` and `$CrossesOnTop` cases. Judged again: it holds. `witness --every-case` reports each dropped `$Apart` case (`$StackByBbox`, `$StackRectanglesByBbox`, `$OpenDirOpposite`, `$SolidCountsClosed`, `$CrossingSinks`, `$ClosedAgainstDiagonal`, `$ClosedInGrid`, `$Components8`, `$Components8 & $CrossingSinks`) as failing Subsumption against the matching `$CrossesOnTop` case. The branch models the Analyze report names are therefore not cases, and the case standing for each takes `$RectanglesOnTop` or `$CrossesOnTop`. That is why the run against the Analyze file prints, on `kinds-meet`, defined grids for the cases standing for `$ClosedAgainstDiagonal`, `$CrossingSinks`, `$SolidCountsClosed`, `$OpenDirOpposite`, `$StackByBbox` and `$Components8`, where the Analyze file gives those branches undefined.
- (create) The witness file gains `tailed-box`, `background=DominantColor` (written by `derive`), and `open-meet`. `open-meet` is the `kinds-meet` grid with the cross moved one column right, so that no shapes close a region off together. It separates the dropped case `$ClosedInGrid & $Apart` from the `$ClosedInGrid` cases with `$RectanglesOnTop` and `$CrossesOnTop`, which the `--every-case` run needs to reach that case's Subsumption failure.
- On `joint-pocket`, the solver's `$StackByBbox` cases sink all four crosses two rows, and the Analyze file gives `$StackByBbox` 2 rows for the cross of 6, 1 row for the crosses of 3 and 4, and 0 rows for the cross of 2. The bounding boxes of the four crosses overlap in that input (the 2 box shares (3,3) with the 3 box and (3,5) with the 4 box, and the 6 box shares (5,3) and (5,5) with them). The rule names `Gravity`. In the lib's `Gravity`, a cell two bodies share stops neither, so each body is held only by a body cell strictly ahead of it. The 6 box reaches the bottom edge after 2 rows, and the boxes behind it keep their gaps to it, so all four move 2 rows. The Analyze file's grid comes from its probe, which settles overlapping bodies another way. The Analyze file erred, and the witness file keeps the solver's grid. `joint-pocket` is a `$ClosedInGrid` witness. On it, the concept and `$StackByBbox` differ in both files.

## Judgments
- Simplify: `gap` now reads `box_cell` (`gap(Sh) :- box_cell(Sh, P), !shape(Sh, P).`) in place of a second bounding-box test over `off_shape`, and `box_cell` moved up beside the `Bbox` instance that both the kind test and the contact branches read.
- The `@ignore: derive concept` reason now says which case gives the concept base's derived output: the case that takes `$RectanglesOnTop` and the derived background.
- (create) Kind by color fails Fit. In train 0, the color-1 box at rows 2–4, cols 1–3 rises, and the color-1 cross at rows 4–7, cols 12–15 sinks.
- (create) Kind by bounding box fails Fit. In train 0, the box of 1 and the cross of 2 both have a 3x3 bounding box.
- (create) Kind by size fails Fit. The test0 cross of 2 at rows 1–4, cols 10–14 has 8 cells, the same count as the train pairs' 3x3 boxes. The test0 box of 1 at rows 6–10, cols 10–14 has 16 cells, a key no train pair has (Unseen key).
- (create) The settling order within one kind fails Equivalence, as the Analyze report states.
- (create) `tailed-box`: plausibility borderline, verdict concept, `@relaxed two-kinds`. The knobbed outline is neither a rectangle outline nor a cross. A reader takes a rigid shape to stop where its cells meet an obstacle.
- (create) `open-meet`: plausibility borderline, verdict concept. It is the `kinds-meet` situation without a joint pocket. It has no `@witness` line, because it serves to separate a pair of cases.
- (create) `t-shape` takes `@relaxed two-kinds`: a cross with no arm above its bar is not a cross with four arms.
- (create) The common-subexpr hint on `rise.dir` and `sink.dir` was resolved by reading the sink keys off `rise.dir`.
- (create) The common-subexpr hint on `risen` and `sunk` is kept with `@ignore`. The two kinds fall in separate `Gravity` instances, and each instance draws its shapes at their travel.
- (create) The case-section hint on `$SolidCountsClosed` reading `rectangle(_, $OwnClosure())` was resolved by deriving that branch from `own.region` directly.
- (create) The test "a cell with all four neighbors in the shape" uses the lib `Rim` in place of a local neighbor clause.
- (create) The rectangles and the crosses fall in two `Gravity` instances, keyed `Rise` and `Sink`. One instance keyed by heading would merge the two kinds whenever `closed_dir` equals `open_dir`, and the concept has the kinds pass through each other.
- `deletions` (as in create): every deletion that changes nothing stays. Each is structure that the pairs never exercise: the bounding-box restriction in `gap` (now the `box_cell` atom), the solid-box clause, the diagonal steps of `own8`, the cardinal restriction in the `$ClosedInGrid` neighbor test, and the meet negations in `out`.
- Determine: `sweep` reports only the stored values, and `determination-plan` lists no actions, so the solver has no `Determine` comp. `derive`, `store` and `audit` report nothing new.

## Open
- none

## Lib
- (create) Closure against corner passage: a `Reach` over the cells outside the shape, with the grid-edge cells as seeds and the eight neighbor steps. A cell that `Reach` does not reach is closed off. This extends a lib comp through its `step` input, so it stays a local clause: `own8.step(V) :- step_offset(_, V).`. The grep finds the same shape in aa4ec2a5 (`open8`, `own_open8`) and a5313dff (`leak`).

## Fixes elsewhere
- none

## Issues filed
- none
