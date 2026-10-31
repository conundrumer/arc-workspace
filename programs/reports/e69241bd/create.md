# e69241bd

## Departures
- Constructor `$SingleCell` in `SeedSet`, with witness `two-cell-seed` (borderline, verdict concept, `@relaxed seeds`): Develop step 3 forms the Not formed item "a seed is a single cell, with a size test". That item states one model, and the model fits every pair. The size test is written as "no such cell beside it". For a 4-connected piece, that test is the same as size 1.
- Choice point `WallSource` with constructor `$SecondCommonest`, and witnesses `walls-outnumber-floor` (variant, concept) and `seeds-outnumber-walls` (borderline, concept): Develop step 3 forms the Not formed item "`wall` as the second commonest color". 5 is the second commonest color in every input, so the model fits every pair. The model is written with `Tally` and `Order` (`next` below `last`), which have a relational form. `walls-outnumber-floor` uses the input of `background=DominantColor`.
- `@derive RarestColor: ordinary concept` on `seed_colors`, and witness `repeated-seed-color`: `derive` reports that `seed_colors=RarestColor` fits, and `analyze.md` does not give it. On `unseen-seed-color`, the output of that derived branch is the concept's output. On `repeated-seed-color` (two seeds of 3, one seed of 6), only the 6 room fills.
- The witness id `background=DominantColor` cannot be the id on a `@witness` line, because lint wants a slug. The `@derive DominantColor` line records the witness. The `$SecondCommonest` branch has its own witness, `walls-outnumber-floor`, on the same input.
- `$Adjacency8` and the failing `background`/`wall` derivations have no constructor: `analyze.md` gives them no witness, and they fail Fit at train0.
- `record --all` added cases to the groups of the witnesses from `analyze.md`: on those witnesses, `$SecondCommonest` and `$SingleCell` give the outputs that the groups now show. `witness --file programs/reports/e69241bd/witnesses.json` reports no difference.

## Judgments
- Hints for "case section" at the first run: the `reach` instance was keyed by color alone, so cases of one seed reading could read seeds of another. I keyed `reach` and `nearest` by the `SeedSet` and `WallSource` fields, and `rooms` by `WallSource`. These are inputs that vary per case.
- Hint "determine prediction" on `Determine.wall`: I kept the relation with `@ignore`. 0 and 5 both stand in every input and every output, so only a test that reads input and output together tells them apart. The sweep finds 5 unique.
- `seed_colors` sweep: one single-row change also gives every train output. `analyze.md` gives no open parameter, so the stored set stays as the train seed colors.
- Not formed items left out: "closed rooms only" and "eight-neighbor interior" fail Fit (see `analyze.md`). "Paint through doorways" states no single model, because the inputs have no doorways.
- `deletions`: the remaining no-change deletions are concept atoms that the pairs do not exercise (`floor`, `beside_mark`, `room_cell(W, Q)` in the walk edges) or the case gating `impl_choice`. I kept them all. I removed the enumerator atoms in the `seed` and `wall` clauses and `color_count.domain`.
- Plausibility of the witnesses I built:
    - `two-cell-seed`: borderline concept. It breaks `seeds`.
    - `seeds-outnumber-walls`: borderline concept. It needs very sparse walls in a one-row grid.
    - `walls-outnumber-floor`: variant concept, as `analyze.md` gives for that input.
    - `repeated-seed-color`: ordinary concept. A seed color that repeats across rooms breaks no scene claim.
- Keywords: `objects markers flood`.

## Unsettled
- The `Determine.wall` relation reads input and output together. A determination by fit over the color type would settle whether the `@ignore` is needed.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
