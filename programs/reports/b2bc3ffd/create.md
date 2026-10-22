# b2bc3ffd

## Departures
- `$OverflowUndefined` has no constructor and no case: it fails Subsumption. Wherever it is defined, no object leaves the grid, so its grid is the grid of the same reading with `$Lost` or `$Clamp`. The Analyze report says the same, and `witness` found no run that shows it defined and differing from `$Clamp`. The witness file no longer names it.
- `impl_choice` holds `$Clash` only in the concept case. Each other reading with `$Clash` fails Subsumption: it is undefined where two objects of different colors land on one cell, and elsewhere it gives the grid that the same reading with `$LargerOnTop` gives. `witness` flagged 7 such pairs among the witnessed cases, and the same argument holds for every base. So each branch's model, for example `$ColorClass`, now stands as the case that takes the branch and `$LargerOnTop`.
- `$FloorMoves` is a constructor although the Analyze report gives it no witness on its own. Its cases are the combinations that fit: `$GroundedOnly` with any overflow reading, and `$FromPlace & $Wrap`, where the 8-cell floor line wraps round to its own place. Both are limited to one-color objects (`$OneColor` or `$ColorClass`). With `$MultiColor`, the floor line joins every object that stands on it and fails Fit. Its witness line is `floor-colored-object: borderline concept`, where the Analyze report sets `$FloorMoves & $GroundedOnly` apart from `$GroundedOnly`.
- `$Wrap` is a new branch of `overflow`, formed from the Not formed item "cells past the far edge wrap to the floor side" (Develop step 3). It fits every pair because no pair overflows. It has a relational form: each line along the heading is a cycle, and the cells walk round it with `CycleWalk`. Its witness is `wrap`.
- The `@store` line on `floor_cell` (`variant $FloorDerived`, `@relaxed floor`) adds the branch `floor_cell=stored`. Its witness is `floor_cell=stored`, written by `store`.
- The header's `jump` rule takes the Analyze report's restatement: cells moved past the far edge are lost, and the model is undefined where two moved objects of different colors land on one cell or a moved object lands on a floor cell.
- New witnesses, besides `wrap` and `floor_cell=stored`:
    - `taller-grid` separates `$FloorLineOnly & floor_cell=derived` from `$FloorColor & floor_cell=stored`. It also shows `$FloorMoves & $FromPlace & $Wrap` defined and differing from its `$FloorColor` counterpart.
    - `floating-collision` separates `$LargerOnTop` from `$SmallerOnTop` under `$MultiColor`. In the Analyze `collision` witness, the two colliding objects touch, so under `$MultiColor` they form one object and do not collide.
- The `separates` text of `overflow` now says that the wrapped cells land on the floor line, which gives no grid, in place of the text about `$OverflowUndefined`.
- `witness --file work/task/b2bc3ffd/witnesses.json` reports no difference other than the removed name `$OverflowUndefined`.

## Judgments
- `wrap`: plausibility `borderline`, verdict `any`. It breaks `fits`, and no pair shows what happens past the far edge. This is the same verdict as `overflow`.
- `taller-grid`: plausibility `variant`, verdict `concept`. No scene claim fixes the grid size, but every pair is 8×8. A taller variant keeps its floor. No `@witness` line records it: it is a further witness of the `floor_cell=stored` branch.
- `floating-collision`: plausibility `borderline`, verdict `any`. It breaks `grounded`, as `collision` does with an object over another.
- `floor_cell=stored` line: plausibility `variant`, verdict `$FloorDerived`. Its witness is train 0 turned a quarter turn. On it the generator would move the objects away from the left floor, which is the output of `$FloorDerived`.
- A heading stored apart from `floor_side` is not formed. Redundant value makes it derived data, because the heading is away from the floor in every variant task.
- These Not formed items fail Fit at train 0, so they have no clauses:
    - The other jump measures fail because the 9 object has 4 cells and jumps 4: height 2, width 3, box area 6, edge perimeter 10.
    - A trace in vacated cells fails because every output clears them.
    - The `background` proposers `SharedColor` and `RarestColor`, and every `floor_color` proposer, fail too. `derive` lists only `DominantColor`.
- `$FromFloor` finds where an object lands without arithmetic. It takes a cell of the object nearest the floor, then the floor cell on that cell's line, then the next cell toward the heading. The move to that cell is the object's start, and from there it jumps its count.
- Lint findings were fixed. The literal `1` in "the line next to the floor" became `neighbor(P, D, Q), dist(Q, D, 0)`. The other fixes followed the hints: `jump`, the negated `landing`, the wrapped long clause, and the `cycle.succ` and `out` disjunctions.
- `lift` keeps `@ignore: case section`. The relation is keyed by the floating reading, and each clause feeds only the cases of its own reading. The hint reads the `$Wrap` clause's variable `F` as reaching every clause.
- `deletions` listed 28 deletions that change nothing, and all stay. Each one guards a structure the pairs never instantiate:
    - derived-floor uniqueness;
    - 8-connected multicolor objects;
    - floating objects and overflow;
    - collisions, through `landing.id`;
    - off-frame landings;
    - the column match in the wrap cycle;
    - the undefined output when no floor is found;
    - `impl_choice` in the collision clauses, which keeps out rows to the cases.
- Determine: `sweep` found each parameter's value unique, and `determination-plan` lists no actions, because each value is covered by a built-in determination. The solver has no Determine comp.
- Keywords `objects count move` cover the concept, and no new keyword is needed.
- Performance: a run takes 7–12 s, and the final audit took 44 s. The first audit, with 2160 cases before the Subsumption drops, took 3 min 14 s.

## Open
- The `background=DominantColor` and `floor_cell=stored` cases built on the concept base take `$Clash`, so each is subsumed by its `$LargerOnTop` counterpart. The audit does not flag them. A ruling would settle it: whether an `@ignore: derive $Clash` or `@ignore: store $Clash` line belongs under those lines.
- Under `floor_cell=stored`, a case does not read its `FloorExtent` field. So the cases that differ only in that field have one model. The audit reports no Equivalence finding for them. A ruling on how a `@store` branch meets a `Choice` field that it makes unread would settle it.

## Lib
none

## Fixes elsewhere
none

## Tickets filed
- 10-295_task_b2bc3ffd_create.md
