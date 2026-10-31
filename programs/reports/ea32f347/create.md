# ea32f347

## Departures
- `$UndefinedAtTies` has no constructor, no clauses and no name in the witness file: it fails Subsumption. `witness` found no run where it is defined and differs from `$CompetitionRank`, because wherever it is defined it gives the concept's output. `analyze.md` predicted this. With the branch gone, `witness --file programs/reports/ea32f347/witnesses.json` reports only that `$UndefinedAtTies` names no case.
- The `$NonBackground & background=DominantColor` witness was removed. `derive` recorded the witness `background=DominantColor` for the same `@derive` branch: train 0 on a field of 3.
- The witness file has an added witness, `mixed-bar-colors`. It resolves the case pair that no witness separated, `$NonBackground & background=DominantColor` against `bar_color=RarestColor`. On it, the shortest bar is drawn in 8 and the other two in 5. The rarest color, 8, makes that one bar the only bar, so it takes 1 and the 5 bars stay. The non-background reading ranks all three bars 1, 4, 2.
- The concept branch constructors take names of my own: `$RankFromLongest`, `$DenseRank`, `$CellCount`, `$FourConnected` and `$BarColor`. The choice point `color-from-order` is the type `Direction`, because the lib owns the name `Order`.

## Judgments
- `mixed-bar-colors`: plausibility `borderline`, verdict `$NonBackground`, relaxed `straight-bars`. Bars in two colors break the scene, and a generator that did that would most likely recolor every bar by rank.
- `rank_color` and `ascending_rank_color` are two Params relations, not one relation with a case column. They are distinct parameters, because this task admits no value common to both (rank 0 → 1 against rank 0 → 2).
- `impl_choice` leaves out `$ExtremesAndRest & $CompetitionRank`. `$ExtremesAndRest` reads no rank, so that combination has `$ExtremesAndRest`'s model. `$ExtremesAndRest` is a case only with `$DenseRank`, the concept tie branch.
- Sweep: `rank_color` and `ascending_rank_color` admit 40 single-row changes each that give every train output. Each such change adds an entry at a rank that no train input has, or a second color at an existing rank. Neither is an open value a reader of the concept could take, so the stored sets stand.
- Deletions:
    - The `impl_choice` atom in the first `out` clause is implied by `paint`, which never holds `$ExtremesAndRest & $CompetitionRank`. It stays, because `deletions` was the last check before the report and a later edit would have needed another run.
    - The `$RankFromShortest & $CompetitionRank` rank rule, the `!ends.low`/`!ends.high` tests and `uncommon` in Determine act only on structures that the pairs do not have: ties, inputs where all bars have one length, and inputs with another field color. They stay.
    - The `axis_elem` enumerator stays, as the tool states.
- Hints: the case-section hints on clauses that hold case values of two points were resolved with `&` markers. The pass-through hint on `role` was resolved by folding `role` into `paint`.
- `derive` printed `$ExtremesAndRest & $NonBackground: emits nothing` on its background witness. The stored background 0 makes the whole field one piece, so every bar has one length, and `$ExtremesAndRest` is undefined there by its rule.

## Unsettled
- Determine repeats the program's parse (Components, Tally, Ordinal over the bar cells), keyed by `Example` in place of the program's `View`. It was not moved into a shared `Parse`. To settle it, write a `Parse<Key>` that both the program, keyed by cells reading, adjacency and measure, and Determine, keyed by example, instantiate.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
