# d90796e8

## Departures
- The witness file's groups are rewritten by `record --all`. In `background=DominantColor`, the concept group is now `$AnyPartner & background=stored`, and `background=DominantColor` no longer sits beside `concept` in the `red-between-two-greens` group: a name denotes only witnessed cases. The cases `$ExclusivePair & background=DominantColor` and `$IsolatedPair & background=DominantColor` show no output that a case with fewer of their non-concept branches does not also give, so they are not witnessed. No grid changed: `witness --file programs/reports/d90796e8/witnesses.json` passes.

## Judgments
- Constructors: `$IsolatedPair` and `$ExclusivePair` are branches of one point, `pair-condition`, so the Choice is one ADT. `AnyPartner` is the name I gave the concept branch. `$EightAdjacent` and `$PositionalKeep` have no witness in `analyze.md` and fail Fit, so they get no constructor.
- `background=DominantColor` is a `@derive` line on `background` (`foreign derived`, `@relaxed scattered-single-cells`), not a constructor. `derive` lists it as the only built-in derivation that fits. `store` reports nothing.
- Not formed: every item fails Fit, is undefined on every pair, or adds no model, as `analyze.md` gives, so Develop step 3 forms no branch.
- Determine: `result_color` is the color a changed cell takes that is absent from that input; `merge_color` is the input color of a cell that changes to it; `absorbed_color` and `background` are the input and output colors of the other changed cells. These read only examples with `ex_out`. The sweep gives one value for each parameter, and the plan then lists no actions.
- `deletions`: 9 deletions change nothing. All of them are the `$IsolatedPair` and `$ExclusivePair` clauses. They matter only where a pair touches a third non-background cell or a cell has two partners, and no pair of the task has either. The witnesses show both, so the clauses stay.
- Keywords `objects match`: `$IsolatedPair` reads 4-connected objects, and the cells pair off by contact. `merge` would fit the merging into one cell, but its gloss requires like-valued pieces.
- No lint hints. No performance issues: every run finishes in under 5 s.

## Unsettled
- Keyword gloss: `match` says "pair off by a shared property", and here cells pair off by contact. To settle it, widen `match` to "a shared property or a relation such as contact", or widen `merge` to cover pieces of different values.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
