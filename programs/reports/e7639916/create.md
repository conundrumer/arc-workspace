# e7639916

## Departures
- `$ExactCount` has no case in the solver, and the witness `extra-mark` is removed: the `witness` run found no input on which `$ExactCount` is defined and differs from `$AnyCount`. Its model is defined only where it gives the concept's output, so it fails Subsumption, as `analyze.md` says. With that branch gone, `Choice` is `MarkSet` alone.
- The branch `background=DominantColor` is the `@derive DominantColor` line on `bg`, and the witness file names it `bg=DominantColor`. The `derive` run wrote its own witness `bg=DominantColor` (train 0 with 0 and 2 swapped). The witness `analyze.md` gave under that id is kept as a further witness, `field-5`, because its input (a field of 5) differs.
- The branch `mark_color=RarestColor` is the `@derive RarestColor` line on `mark_color`, under `$MarkColorStored`. A run against `witnesses.json` reports that this name denotes no case: alone, the name takes `$NonBg`, which reads no `mark_color`. The solver's witness file gives that model as recorded by `record --all`.
- The concept branch constructor of the mark set is `$NonBg`.

## Judgments
- `@ignore: derive` on `mark_count`: `derive` reported `TileCount` and `SepTileCount`, which take the count from the grid's extent. Each one leaves the `$ExactCount` model defined only where it gives the concept's output, so it fails Subsumption. This note left the solver with `$ExactCount`.
- `@ignore tally: store` on the `$ExactCount` tally: a stored tally of 3 always matches the stored count, so the model is the concept's, and it fails Equivalence. This note left the solver with `$ExactCount`.
- `@derive DominantColor` on `bg`: `variant`, verdict `derived`, `@relaxed scattered-marks`, as `analyze.md` gives it.
- `@derive RarestColor` on `mark_color`: `borderline`, verdict `$MarkColorStored`, `@relaxed scattered-marks`, as `analyze.md` gives it.
- Determination: `outline_color` is the color of every changed cell, and `mark_color` is every color of an input that is not `bg`. `bg` has no determination relation. The plan lists `bg (DominantColor exact)`, but the commonest color is the field, and the concept takes the background from the field too.
- Keywords: `markers` (the marks fix the box's extent), `bbox`, `border` (the drawn outline).
- The audit found no stored fact whose removal changes no output.
- Simplify: `deletions` found that every deletion it tested changes the result.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
