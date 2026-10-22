# b5bb5719

## Departures
- `read_side` is not a stored parameter. Params stores `read_sense(SENSE_CW)`, and the program derives the read side as a quarter turn in that sense from the grow direction. Because of this, `$GrowFromSeedEdge` has no undefinedness on the read side's axis, and on `seed-at-bottom` it grows upward and reads the right neighbor, so it gives `7 7 5 7 7` on row 1 where the Analyze file gives `7 7 2 7 7`: Style > Params "Relative orientation". The read side is perpendicular to the grow direction in every variant task, and only the sense varies.
- `$DiagonalHead` is a branch of `fill-color` that the Analyze report puts under Not formed as equivalent to the concept: it is not equivalent. The concept colors a cell from its nearest filled read-side ancestor. `$DiagonalHead` reads the cell on the seed edge's line. The two part where ink lies off that line. Witness `inner-seed` (row 0 `5 7 7 7 7`, row 1 `7 5 7 5 7`) gives 2 at (2,2) under the concept and 5 under `$DiagonalHead`. It meets Fit and Relational form (`CycleWalk` over `swap`, stepped by the cell's distance to the seed edge).

## Judgments
- `inner-seed` is `borderline concept`, `@relaxed seed-row`: it puts ink on two rows, which only an unusual generator run would give, and a reader would still color by the upper-left neighbor.
- The three `@store` lines that `store` offers on `off_edge`, `seed_edge.item` and `seed_edge.value` carry `@ignore: store` for Equivalence: each stored value fixes one grow direction, which is the `$StoredGrow` model, and the stored case takes more non-concept branches.
- `swap` is determined as the pairing of the input colors outside `background`. This is position-free and does not repeat the program's geometry.
- Deletions judged: the background test in `fill.join`, `!seed` in `filled`, `grow(H, _)` in `out`, `axis_of` in `span.axis`, the `filled` guards on `paint.edge` and `paint.join`, and `hue(Col) :- params.swap(_, Col)` stay. Each one states a rule or an undefinedness, or is needed off the train pairs (the test input holds only 5, so `$MixedTakesOtherSide` needs 2 in `hue` from its row 2 on). The `impl_choice` atoms in the per-paint clauses were removed, because every combination is a case and the other atoms bind the fields.
- Two `Propagation` instances carry the recursive rules. `fill` grows the filled set through `join` on the two diagonal neighbors. `paint` grows (cell, color) marks, through `edge` for `$SwapSide` and through `join` for `$MixedTakesOtherSide`.
- `$SpanTriangle` seeds `fill` with every cell that `Between` places between ink cells across the grow axis, so the triangle is the same join grown from the span.
- Keywords: `walk` (row-by-row propagation from the row before) and `mapping` (the swap).

## Open
- none

## Lib
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-370_task_b5bb5719_create.md
