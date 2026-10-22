# b2bc3ffd

## Departures
- `$OverflowUndefined` has no constructor and no case, and the witness file does not name it. It fails Subsumption: wherever it is defined, no object leaves the grid, so its grid is the grid of the same reading with `$Lost` or `$Clamp`. The Analyze report says the same. The departure holds. (create)
- `impl_choice` holds `$Clash` only in the concept case. Each other reading with `$Clash` fails Subsumption: it is undefined where two objects of different colors land on one cell, and elsewhere it gives the grid of the same reading with `$LargerOnTop`. So each branch's model, for example `$ColorClass`, is represented by the case that takes the branch and `$LargerOnTop`. The departure holds. (create)
- `$FloorMoves` is a constructor although the Analyze report gives it no witness of its own. Its cases are the combinations that fit: `$GroundedOnly` with any overflow reading, and `$FromPlace & $Wrap`. All of them have one-color objects (`$OneColor` or `$ColorClass`). Its witness line is `floor-colored-object: borderline concept`, the input on which the Analyze report sets `$FloorMoves & $GroundedOnly` apart from `$GroundedOnly`. The departure holds. (create)
- `$Wrap` is a branch of `overflow`, formed from the Not formed item "cells past the far edge wrap to the floor side" (Develop step 3). It fits every pair, because no pair overflows. Its relational form walks each line along the heading as a cycle, with `CycleWalk`. Its witness is `wrap`. The departure holds. (create)
- The `@store` line on `floor_cell` (`variant $FloorDerived`, `@relaxed floor`) adds the branch `floor_cell=stored`, and `store` wrote its witness. The departure holds. (create)
- The header's `jump` rule uses the Analyze report's restatement: cells moved past the far edge are lost, and the model is undefined where two moved objects of different colors land on one cell or a moved object lands on a floor cell. (create)
- Create built these witnesses, beside `wrap` and `floor_cell=stored`: `taller-grid` and `floating-collision`. The `overflow` witness's `separates` text describes `$Wrap` in place of `$OverflowUndefined`. (create)
- `// @ignore: derive $Clash` under the `@derive DominantColor` line, and `// @ignore: store $Clash` under the `@store` line on `floor_cell`. Each records that the concept base with that branch is subsumed by the same base with `$LargerOnTop`, for the reason the `$Clash` departure gives. This settles create's first open item. With those cases gone, the `$LargerOnTop` counterparts stand for those branches, and the witnessed cases rose from 68 to 70.
- `// @ignore: store $FloorLineOnly` and `// @ignore: store $FloorMoves` under the `@store` line on `floor_cell`. Under `floor_cell=stored`, `FloorExtent` is read only through `floor_cell`, so a case with `$FloorLineOnly` or `$FloorMoves` is equivalent to the same case with `$FloorColor`. It takes one more non-concept branch, so it fails Equivalence. This settles create's second open item.
- `record --all` re-recorded the witness file after those changes. `floor_cell=stored` has the group `$Clash & floor_cell=stored` renamed `$FloorStored & $OneColor & $FromPlace & $Lost & floor_cell=stored`. The other witnesses have only their groups reordered.
- `witness --file work/task/b2bc3ffd/witnesses.json` reports no difference other than the removed name `$OverflowUndefined`.

## Judgments
- `wrap`: plausibility `borderline`, verdict `any`. It breaks `fits`, and no pair shows what happens past the far edge. (create)
- `taller-grid`: plausibility `variant`, verdict `concept`. No scene claim fixes the grid size, and a taller variant keeps its floor. It is a further witness of `floor_cell=stored`, so no `@witness` line records it. (create)
- `floating-collision`: plausibility `borderline`, verdict `any`. It breaks `grounded`. (create)
- `floor_cell=stored` line: plausibility `variant`, verdict `$FloorDerived`. Its witness is train 0 turned a quarter turn clockwise. (create)
- A heading stored apart from `floor_side` is not formed. Redundant value makes it derived data. (create)
- The other jump measures, a trace in vacated cells, the `background` proposers `SharedColor` and `RarestColor`, and every `floor_color` proposer fail Fit at train 0, so they have no clauses. (create)
- `$FromFloor` finds where an object lands without arithmetic. It takes a cell of the object nearest the floor, then the floor cell on that cell's line, then the next cell toward the heading. (create)
- `lift` keeps `@ignore: case section`. The relation is keyed by the floating reading, and each clause feeds only the cases of its own reading. (create)
- `deletions`: 28 deletions change nothing, and all stay. Each one guards a structure that the pairs never instantiate: derived-floor uniqueness, 8-connected multicolor objects, floating objects and overflow, collisions, off-frame landings, the column match in the wrap cycle, the undefined output when no floor is found, and `impl_choice` in the collision clauses. (create; the same list this pass)
- Simplify: the `Jump` record was not a type that [Types](docs/handbook/solver-file.md#types) allows, because no comp takes it as a type argument. `Spot` now holds the case fields and the cell directly, and `landing` is keyed by `Spot`.
- Simplify: `escapes` and the `landing` clause from `drift` now stand under the markers of the cases that read them (`$Clamp`, and `$Lost, $Clamp`). `floor_color` for each source stands under `& $FloorColor`.
- Simplify: replacing `mixed_edge` and `uniform_edge` with `Unanimous<Dir, Color>` was tried and reverted. `edge.value` holds `(DIR_T, 7), (DIR_B, 8)` on every input, so `store` asked for a new `@store` branch. That would change the cases, which Simplify keeps as they are.
- Lint hint `case section` on `.init box` under `// --- $FromFloor, $Clamp ---`: the hint reads the `$Wrap` landing as reaching `box` through `lift`'s `$FromFloor` clause. That is the same false reach as on `lift`. `box` stays under `// --- shared ---`, as create left it.
- Determine: `sweep` found each parameter's value unique, and `determination-plan` lists no actions. The solver has no Determine comp. (create)
- Keywords `objects count move` cover the concept. (create)
- Performance: a run takes 3–7 s. The audit takes 26–45 s.

## Open
none

## Lib
none

## Fixes elsewhere
none

## Tickets filed
- 10-298_task_b2bc3ffd_refine.md
