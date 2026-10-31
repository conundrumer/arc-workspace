# be94b721

## Departures
- The groups in the witness file name cases (`$Conn4`, `$ShapeCells`, `background=stored`, `$Conn4 & background=DominantColor`, `$Conn8 & background=DominantColor`) where `witnesses.json` names branches. On the `background=DominantColor` witness the file also gives a third output, from `$Conn8 & background=DominantColor`. `record --all` wrote these. They are what [Witness file](docs/handbook/solver-file.md#witness-file) asks of the solver's file. `witness --file programs/reports/be94b721/witnesses.json` reports ok, so no branch's output differs from the one `witnesses.json` gives it.

## Judgments
- The `Choice` is `[shape: Shape, content: Content]`. `Shape` has `Conn4` (the concept, a name I chose), `$Conn8`, `$ColorClass` and `$AnyColorComponent`. `Content` has `ShapeCells` (the concept, a name I chose) and `$BoxRegion`. The cases are all 8 combinations, and every one fits every pair. `background=DominantColor` is a `@derive DominantColor: borderline concept` line on `background`, not a constructor: `derive` reports that it fits. The run shows 7 witnessed cases, and all 5 pairs pass.
- `size-measure` has no constructor. `analyze.md` gives `$BboxArea`, `$Height` and `$Width` no witness, and each fails Fit (train1, train1, train0).
- The Not formed items need no new branch. A tie rule states no model. A stored kept color, fewest cells, rarest color and a fixed output size each fail Fit at a train pair, so no combination that takes one could be a case.
- Parse: one `member(Shape, Ident, Position)` relation fed by each shape reading. `$Conn4` uses `Components<Color>` and `$Conn8` uses `Components8<Color>`, each keyed by color over non-background cells. `$AnyColorComponent` uses `Components<Unit>` over all non-background cells. `$ColorClass` uses `IdentOf<Color>`, which gives each color one id as its single shape. Ids from different instances can collide, because each id is a position's `ord`, so `Tally` is keyed by `Obj = [shape, id]`. Then `ArgExtremes<Shape, Ident>` finds the largest, `Unanimous` (`@claim one-biggest`) makes a tie undefined, `Bbox<Shape>` boxes the kept shape, and `crop` places it.
- Determination: `Determine.background` keeps each color that every train input holds, through the defect relation `absent`. The field is in every input, while the shapes' colors vary. This gives {0}. Before I wrote it, `determination-plan` asked for a determination relation for `background` (DominantColor exact). Now it reports no actions, and the run reports `determination: ok (background)`.
- `sweep`: `background` has the unique value 0, so no value was stored beyond the stored one.
- `store`: no findings. Lint: ok, and no hint fired.
- `deletions`: removing the atom `kept(Sh, P)` in the `$ShapeCells` `out` clause changes no pair. I keep it: no pair has another shape's cell inside the kept box, but the `cell-in-box` witness does, and without the atom that cell gets two colors.
- Witnesses: I built none. All 5 come from Analyze, with plausibility and verdict as `analyze.md` gives them. `witness` (both files) and the final audit report ok, with no unseparated case pair, no unwitnessed case and no redundant fact.
- Keywords `objects crop rank select color-class`: `rank` because the largest by cell count picks the shape, `select` because the output keeps one part of the input, and `color-class` for `$ColorClass`.
- I did not read `src/`.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
