# d304284e

## Departures
- `$TurnSense` is a constructor of `BranchDir` (the drop way is a quarter turn in a stored `branch_sense` from the run's way), and every combination that takes it is a case. `analyze.md` lists it under Not formed as equivalent to the concept. This rests on three things. The dropped-cases audit found that `$TurnSense` alone fails no case condition. The two models are not equivalent as defined: at a concept assignment whose `branch_dir` lies on the run's axis, the concept is undefined on every input, and no `$TurnSense` assignment matches that. Witness `turn-sense` reassigns `march_dir` to left: there the concept keeps the drops down and `$TurnSense` sends them up. With `$MarchToRoom` it gives a further distinct output on `march-to-room` (the run goes left, the drops go up).
- `$MarchToRoom` on a tie: the solver draws the run toward every tied way in one grid, and its `@rule` line says so. `analyze.md` gives one grid per tied way. One grid per way would need a `TiebreakResolution` column chosen per unit, which under `$PerObject` is a product over units. No pair or witness has a tie.
- The concept branch of `unit` (`WholeInk`) has `@claim march`, since `$PerObject`'s line changes `march`.
- Built-in derivations and stored values held as branches: `background=DominantColor` (from `analyze.md`, as `@derive DominantColor: foreign concept`), `shape_color=RarestColor` (`@derive RarestColor: variant derived`, under `$RecolorShapeColor`), and `paint=stored` (`@store: borderline concept` on `paint`, the color each marked ink color takes). Their witnesses `shape_color=RarestColor` and `paint=stored` were added to the witness file, along with `turn-sense`.
- The witnesses `shape_color=SharedColor` and `shape_color=VanishedColor`, which `derive` wrote, were removed: no case of the solver has those names (see Judgments).
- `Parse.ink` has no color column, and readers join `in` for the color. With a color column, `store` asks for the ink color 7 to be stored as a parameter. The same `store` finding led the earlier, interrupted pass to strip color columns from `member`, `copy`, `marked_cell` and `dropped`, which now carry the source cell.

## Judgments
- This pass picks up an earlier `create` pass that was interrupted at its audit call. From that pass I kept the solver's structure, its six choice points, the `@derive`/`@store`/`@ignore` lines and the witness file. I then did Develop step 3 and everything after it.
- Witness `turn-sense`, `variant concept`, `@reassigned march_dir`: reassigning `march_dir` alone gives the left-right mirror of the task. There the generator keeps the stored drop way, down.
- Witness `paint=stored`, `borderline concept`, `@relaxed one-shape` (earlier pass, checked): train1's ring with a center of color 2. A two-color shape breaks `one-shape`. The generator paints the whole marked copy, as on `recolor-shape-color`, whose verdict is `concept`. The stored paint maps only 7 to 6, so the copied center is never painted and keeps the background.
- Witness `shape_color=RarestColor`, `variant derived`, `@relaxed one-shape`: train0 with colors 7 and 1 swapped. A shape of color 1 breaks `one-shape` (color 7), and a color permutation is a variant. The generator paints the marked copies. The derived value 1 does that; under `$RecolorShapeColor` the stored 7 does not.
- `@ignore: derive SharedColor` and `@ignore: derive VanishedColor` fail Equivalence. On an input alone, each gives every color of that input. Every ink cell then takes the mark color, exactly as under `$PaintAll`.
- Hint `head-zero` on `pitch`: kept with `@ignore`. Under `$StoredStride` the zero is the absent gap in the period that `stride` reads.
- `deletions`: I removed the atoms that another atom already implies: `branch` in `dropped`, since `drop.ray` holds only the branch ways; `train(E)` in `shape_color`, `plain.shape` and `marked.shape`; `run_way` in `nearest.cand` and `number.item`; and the `clear.cell` rule. I kept the rest because they encode structure the pairs never exercise. That covers `stalled` and `!stalled` (where `$MarchToRoom` is undefined), `perp_dir` in `$StoredBranch`, `branch.d_march` (runs that tie), and the color columns of `paint` and `dropped` (shapes of several colors). It also covers the `$RecolorShapeColor` test and the `parse.ink` atoms in `paint`, plus `color_defect`. In `march_gap` and `drop_gap`, `run_way` and `marked.occurrence` stay: if the shape itself were marked, they keep the gap read on the run's axis and from the drops.
- Determine reads each value from the train outputs. It finds the whole copies of the input ink in each output (`Occurrences`), in the ink's own colors and in the mark color. `march_stride` is the nearest copy in line with the ink, and `march_dir` is that way. Each copy's number is the count of in-line copies up to it. `marked_numbers` are the numbers of the marked copies, and `period` is the first of them. `mark_phase` is each marked number's place in the period. `march_gap` and `gap` are the background runs just past the ink and just past a marked copy toward its drop. `branch_dir` is that drop way, and `branch_sense` is the turn from `march_dir` to it. `shape_color` keeps each ink color present in every train input, a fact of the inputs alone. The plain reading gives 7 and 2 on `recolor-shape-color`.
- `background` (`DominantColor`) and `mark_color` (`AnyOutNewColor`) have no determination relation. Each proposer reads the fact the concept reads: the field is the commonest color, and the mark color is the color new to the outputs.
- `sweep`: 21 single-row changes of `marked_numbers` reproduce every train output, because they add copy numbers no pair reaches. `analyze.md` gives no open parameter, so {3, 6} stays.
- Performance: with 1296 bases, a solver run takes 10–45 s, the audit 285 s, `store` 161 s, and `record --all` 14 s. No workaround is needed.
- Branches dropped under a case condition, all for Fit as `analyze.md` gives: `$MarchBothWays`, `$BranchBothWays`, `$WholeCopiesOnly`. The Not formed readings fail too: marks counted from the far edge or by column residue, one stride on both axes, drops in the shape's own colors, and `mark_color` as `OutNewColor`, which is undefined on every pair's input.
- No rule is approximated. Keywords are unchanged (`objects cast count rank`), and I propose no new keyword. I did not read `src/`.
- Final runs: train 0, train 1 and test 0 pass, with 16 witnessed cases. Lint is ok and the determination is ok. `witness` with and without `--file` is ok, and every audit section is ok.

## Unsettled
- `determination-plan` still asks that `march_stride` give 4 with the pair of `stored-stride` or `mark-set` added, and that `marked_numbers` give {3, 6} with the pair of `mark-set` added. Those are the witnesses on which `$StoredStride` and `$MarkSet` diverge from the concept, so any relation that reads these values from the evidence changes with the pair added. Settled by a runner rule that leaves out a parameter of the case that the witness separates, or by a doc line on what such a relation should keep.
- Grids on a `$MarchToRoom` tie (see Departures): settled by a `TiebreakResolution` encoding of per-unit run ways, or by a judgment that the union is the branch's model.
- Whether `$TurnSense` alone is a case depends on whether Θ holds `branch_dir` values on the axis of `march_dir`. If it does not, `$TurnSense` alone is equivalent to the concept and only the combinations with `$MarchToRoom` would stay. Settled by a ruling on Θ for a pair of parameters bound by a relation such as `perp_dir`.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
