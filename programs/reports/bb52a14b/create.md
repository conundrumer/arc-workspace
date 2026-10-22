# bb52a14b

## Departures
- On `stray-in-key-blank`, the `key_dim=stored` case gives the concept's output (the input unchanged), and the Analyze file gives it undefined: the `@store` branch replaces only `key_dim` and keeps the concept's key rule. That rule takes the one box of the key's extent that holds every mark, whatever its other cells hold, and tests for `background` only to choose among several such boxes. A test on the one box would make the concept undefined wherever the marks' bounding box holds `background`, and the concept is defined on that witness. The witness file groups `key_dim=stored` with the concept on that witness.

## Judgments
- Constructors are `$AnyUnderMarks` with `$KeepUnderMarks` nested under its `fill` field, and `$InkOnlyMatch`. The concept branches take the names `BareMarks`, `FillEveryMark` and `MatchBlanks`: the Analyze report names them `concept`.
- `$CongruentCopies`, `$IsolatedCopies`, `$KeyComponent` and `key=stored` have no constructor: the Analyze report gives them no witness, and each fails Fit.
- `key_dim` is the relation the `@store` line stands on, as the Analyze report's `key_dim=stored` branch needs. The program finds the key through it, as the box of that extent that holds every mark. With the derived extent, that box is the marks' bounding box, so the concept is unchanged.
- No item under Not formed states a model: `SharedColor`, `OutNewColor`, `ChangedColor` and `UnchangedColor` give no single color, overlapping copies have no reading that differs, and a key with no marks or no ink leaves every case undefined alike.
- `store` also listed `key_frame.cell` and `key_frame.extent`, with no witness. Both follow from `key_dim`, so storing them gives the `key_dim=stored` branch again. They have no `@store` line.
- `derive` gave `background=DominantColor` and `fill_color=RarestColor`. Their `@derive` lines take the Analyze report's plausibility and verdict.
- Witness `rare-key-clump`, which I built: plausibility `borderline`, verdict `concept`. It breaks no scene claim. It breaks the invariant that `fill_color` is the rarest color of each input. It shows `fill_color=RarestColor & key_dim=stored` defined and differing from `key_dim=stored`, which `witness` reported that no run showed.
- Determine derives `background` and `fill_color` from the cells the train outputs change, as the plan listed.
- The sweep found that `$FillEveryMark` admits `background` 0, 1 and 8. The concept fixes `background` at 0, and 0 serves every case, so `background` is not an open parameter and has no case column.
- `deletions` found 19 deletions that change nothing. Each removes structure the pairs do not exercise: a branch's distinction, the choice of key under a stored extent, or the test that a candidate box lies inside the grid. All stay.
- Simplify: `key_cand` tests that the marks' bounding box lies inside the candidate, in place of a relation of boxes that miss a mark.
- Two `common-subexpr` hints, on `bare_rival` and on the Determine relations, were resolved by factoring out `rival` and `change`.
- Keywords `noise stamp repair`: scatter cells surround the copies, the key's marks stamp onto each copy, and each copy's missing marks are restored from the key.
- The solver has 6 bases and 48 cases, of which 8 are witnessed. Every witnessed case passes every pair.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
