# ac2e8ecf

## Departures
- The header adds the rule `kind`, which says that a shape that closes off a region by itself, under 4-adjacency, is a rectangle and that every other shape is a cross. The `single-color-objects` scene now says "4-connected". The concept file gives the kind test only inside the scene claim `two-kinds`. The `kind-test` and `shape-parse` choice points each need a claim for their `@claim` to name and for their branches to change.
- `background` has the line `// @derive DominantColor: variant derived`, and `$BackgroundMode` has no constructor. `derive` lists DominantColor as a fitting derivation, and a branch equivalent to a `@derive` branch loses its constructor. The derive witness `background=DominantColor` is train 0 with 0 and 3 swapped. That grid is a routine color variant, and the generator would pair it with the swapped output, which is the derived branch's output. `dense-box` stays in the witness file as a further witness of that branch, and its group is renamed to `background=DominantColor`.
- A new contact branch, `$StackRectanglesByBbox`, makes rectangles stop by their bounding box and crosses by their cells. It is formed from the Not formed item "Bounding-box contact for rectangles alone". The Analyze report's equivalence argument holds only for rectangle outlines. Under the concept kind test, any shape that closes off a region rises. Witness `tailed-box` is a 3x3 outline of 4 with a knob cell. Its cells and its bounding box meet the box of 1 at different steps, so this branch differs from the concept. The branch fits every pair.
- No case takes `$Apart` together with a non-concept branch. `impl_choice` holds the concept case and every case with `$RectanglesOnTop` or `$CrossesOnTop`. A case that takes `$Apart` is undefined exactly where a settled rectangle and a settled cross share a cell, and it equals the matching `$RectanglesOnTop` case everywhere else, so every such case other than the concept case fails Subsumption. The precedent is a09f6c25. The same reason gives `// @ignore: derive concept` under the `@derive` line. The branch models the Analyze report names, such as `$SolidCountsClosed` (which takes `$Apart`), are therefore not cases. For each of them the witnessed case takes `$RectanglesOnTop` or `$CrossesOnTop`.
- The witness file gains three witnesses: `tailed-box`, `background=DominantColor` (written by `derive`), and `open-meet`. `open-meet` is the `kinds-meet` grid with the cross moved one column right, so that no shapes close a region off together. The audit reported that no witness separated the dropped case `$ClosedInGrid & $Apart` from the `$ClosedInGrid` cases with `$RectanglesOnTop` and `$CrossesOnTop`. `open-meet` resolves that pair: on it, the case with `$Apart` is undefined and the others are defined. Every group was re-recorded with `record --all`.
- The run against the Analyze file could not check the grids of the non-concept branches, because their names denote no case. A copy of the Analyze file was made with each branch name `X` rewritten to `X & $RectanglesOnTop` and with `kinds-meet` left out. Run against that copy, the witnesses disagreed with no case's output. On `kinds-meet`, the solver's grids for `$RectanglesOnTop`, `$CrossesOnTop` and `$ClosedInGrid`, and its undefined output for the concept case, match the Analyze file.

## Judgments
- Kind by color fails Fit. In train 0, the color-1 box at rows 2–4, cols 1–3 rises, and the color-1 cross at rows 4–7, cols 12–15 sinks.
- Kind by bounding box fails Fit. In train 0, the box of 1 and the cross of 2 both have a 3x3 bounding box.
- Kind by size fails Fit. The test0 cross of 2 at rows 1–4, cols 10–14 has 8 cells, the same count as the train pairs' 3x3 boxes. The test0 box of 1 at rows 6–10, cols 10–14 has 16 cells, a key no train pair has (Unseen key).
- The settling order within one kind fails Equivalence, as the Analyze report states.
- `tailed-box`: plausibility borderline, verdict concept, `@relaxed two-kinds`. The knobbed outline is neither a rectangle outline nor a cross. A reader takes a rigid shape to stop where its cells meet an obstacle.
- `open-meet`: plausibility borderline, verdict concept. It is the `kinds-meet` situation without a joint pocket. It has no `@witness` line, because it serves to resolve a pair of cases.
- `t-shape` takes `@relaxed two-kinds`: a cross with no arm above its bar is not a cross with four arms.
- The common-subexpr hint on `rise.dir` and `sink.dir` was resolved by reading the sink keys off `rise.dir`.
- The common-subexpr hint on `risen` and `sunk` is kept with `@ignore`. The two kinds fall in separate `Gravity` instances, and each instance draws its shapes at their travel.
- The case-section hint on `$SolidCountsClosed` reading `rectangle(_, $OwnClosure())` was resolved by deriving that branch from `own.region` directly.
- The test "a cell with all four neighbors in the shape" uses the lib `Rim` in place of a local neighbor clause.
- The rectangles and the crosses fall in two `Gravity` instances, keyed `Rise` and `Sink`. One instance keyed by heading would merge the two kinds whenever `closed_dir` equals `open_dir`, and the concept has the kinds pass through each other.
- `deletions`: every deletion that changes nothing stays. Each one is structure that the pairs never exercise: the bounding-box restriction in `gap`, the solid-box clause, the diagonal steps of `own8`, the cardinal restriction in the `$ClosedInGrid` neighbor test, and the meet negations in `out`.
- Determine: `sweep` reports only the stored values. `determination-plan` lists no actions, so the solver has no `Determine` comp.

## Open
- none

## Lib
- Closure against corner passage: a `Reach` over the cells outside the shape, with the grid-edge cells as seeds and the eight neighbor steps. A cell that `Reach` does not reach is closed off. This extends a lib comp through its `step` input, so it stays a local clause: `own8.step(V) :- step_offset(_, V).`. The grep finds the same shape in aa4ec2a5 (`open8`, `own_open8`) and a5313dff (`leak`).

## Fixes elsewhere
- none

## Issues filed
- 1791067840-ac2e8ecf-create-1.md
- 1791067840-ac2e8ecf-create-2.md
