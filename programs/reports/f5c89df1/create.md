# f5c89df1

## Departures
- `$Opaque` has no constructor, and the witness `overlap-hole` is removed from the witness file. It fails Subsumption: where `$Opaque` is defined, its box holes land on no ink, so its output is the concept's. `witness` reported that no run shows it defined and differing, and analyze.md finds no such input.
- `$NoClip` has no constructor, and the witness `copy-past-edge` is removed from the witness file. It fails Subsumption: it is undefined where a copy leaves the grid and gives the concept's output everywhere else. With `$NoClip` gone, nothing denotes `copies-in-frame`, so the header no longer has that `@scene` line.
- `witness --file programs/reports/f5c89df1/witnesses.json` reports only that `$Opaque` and `$NoClip` denote no case. No branch's output differs from the one witnesses.json gives.
- `background=DominantColor` is a `@derive DominantColor` line on `background`, not a constructor. Its witness keeps its id.

## Judgments
- Choice is `[reach: ShapeReach, color: ShapeColor]`, and `$PaintStored` is nested under the concept branch `AnyColor`, as analyze.md nests `stamp-color` under `shape-color`. All 6 combinations fit. With the derive branch there are 5 witnessed cases: concept, `$AnchorComponent`, `$PaintStored`, `$ColorShape` and `background=DominantColor`.
- `pattern_color` is one parameter, read by both `$PaintStored` and `$ColorShape`. No case takes both of them. In a task that both fit, the stamps carry the value each one stores, so both admit the same value.
- `derive` reported SharedColor and VanishedColor for `pattern_color`. On a run's one input, both give every color of that input. Under `$ColorShape` that is the concept's model, so it fails Equivalence. Under `$PaintStored` it paints several colors on one cell, so it fails Fit on every pair. This is recorded as a bare `@ignore: derive`.
- `store` flagged `ink[col]` as one color, 8. Storing that color reads the shape as the cells of a stored color, and that is `$ColorShape` with `pattern_color`. This is recorded as an `@ignore: store`.
- In `second-shape-color`, the concept is undefined: the 4 cell's copies and the 8 cells' copies paint one cell in two colors. witnesses.json gives that too, and the verdict `concept` stays.
- Determine: `anchor_color` is the vanished color that every train input holds at exactly one cell. `marker_color` is the other vanished color. `background` is the commonest color of every input. `pattern_color` is the non-background color of the outputs. `determination-plan` lists no actions.
- `deletions`: the atoms that change nothing are on `$AnchorComponent` and `$ColorShape`, which equal the concept on the pairs, or on clipping (`in(Q, _)`) and on the Determine universals, which the pairs do not exercise. I kept them. The atom `ink(P, _)` in the `$PaintStored` shape clause is implied by `member`, so I removed it.
- Keywords: `markers stamp objects`. `objects` is for `$AnchorComponent`'s component. `bbox` left with `$Opaque`.

## Unsettled
- `deletions` ran before the last solver edit, which removed one atom. A final run of the pairs passed after that edit. A second `deletions` run would confirm that no further deletion changes nothing.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
