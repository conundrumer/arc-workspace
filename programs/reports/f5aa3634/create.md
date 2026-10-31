# f5aa3634

## Departures
- The `background=DominantColor` branch is the `@derive DominantColor` line on `bg`, and the witness file names it `bg=DominantColor`: [Develop](docs/handbook/create.md#develop) step 5 gives that name. The `derive` run wrote its own `bg=DominantColor` witness on the same input, so the copied `background=DominantColor` witness left as a duplicate. `witness --file programs/reports/f5aa3634/witnesses.json` reports only that the name `background=DominantColor` denotes no case.
- `$ShapeOnly` and `$Congruent` are not undefined where the shown class's members give more than two distinct crops, as `analyze.md` states. The solver gives one grid per member through the `TiebreakResolution` column, so such an input gives three or more grids. That still fails test Fit, and no witness depends on it.
- `copies=TileCount` is a `@derive TileCount` branch on `copies` that `analyze.md` does not give. `derive` reported that it fits, so Develop step 4 holds it. Its witnesses are `copies=TileCount` and `six-and-three`.

## Judgments
- Witness `copies=TileCount` (test0's input with a third copy of the 3/8/4 object): `variant`, verdict `derived`, `@relaxed one-repeated-object`. The generator would show the only repeated object. The concept and `$MostFrequent` give the same output there.
- Witness `six-and-three` (a 15x15 grid with a triple and six copies of a 1x2 object): `borderline`, verdict `$MostFrequent`. It was built so that `$CopyCount & copies=TileCount` is shown defined and differing from the concept and from `$MostFrequent`.
- Witness `lone-recolor-and-mirror` (no exact repeat; one recolored twin pair and one mirrored twin pair): `borderline`, verdict `concept` (undefined). It was built so that `$ShapeOnly & $CopyCount` and `$Congruent & $CopyCount` are shown defined and differing from their `$WithColors` and `$Translation` counterparts.
- `store` gave no line for `size_extremes.cand` or `size_extremes.high`, so I added no `@store` line and no `@workaround`. A stored highest class size is `$CopyCount`'s model at `copies` = 2, so that branch fails Equivalence. `class_size.tally` varies by key, and `store` gives no case for it.
- The determination plan listed `bg` (DominantColor exact). The concept takes `bg` as the field color, which is the commonest color of each input, so the plan's fact is the concept's own fact. I wrote no determination relation for it. `copies` has a determination: the count of places where the train output stands in its input, the same over all train examples.
- The `deletions` atoms that gate a clause by a case enumerator, the `$ShapeOnly & $Congruent` clauses, and `ambiguous` stay. The pairs run none of those cases and never hold two repeated classes. `class_size.domain` left: each key already counts itself as a member through `item`. That edit came after the one `deletions` run.
- `match` is a Souffle reserved word, so the sameness relation is `alike`.
- Every combination of the five fields is a base. The run witnesses 11 of 128 cases.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
