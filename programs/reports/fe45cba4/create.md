# fe45cba4

## Departures
- The `$NotchedStays` scene line says the stays-piece's gap is nonempty: `analyze.md` says "Undefined where both pieces, or neither, have such a gap", and a solid piece has an empty gap that reaches no corner. Without the nonempty test, a solid piece would count as notched, and that reading would contradict the undefinedness `analyze.md` gives.
- The witness file's groups were rewritten by `record --all` into the listed case names. The Analyze grids are unchanged, and `witness --file programs/reports/fe45cba4/witnesses.json` reports no difference.

## Judgments
- The constructors are `$SideMoves`, `$NotchedStays` (mover), `$OnePairColor`, `$EveryPairColor` (pair-colors), `$Plug {f: FitTest}` with `$Interlock`, `$FillsNotch`, and `$AreaRectangle` (placement). `$SmallerMoves`, `$RowAlignedSlide` and `$KeyKept` have no witness in `analyze.md` because they fail Fit at train0, so they have no constructor. `background=SharedColor` and `background=RarestColor` fail Fit, and `derive` does not list them.
- `background=DominantColor` is a `@derive` branch at `borderline concept`, as `analyze.md` gives it. `store` printed no line to add: `toward[d]` varies by pair.
- The cases are all 12 combinations of the three `Choice` fields, times the derive point. 6 are witnessed: the concept, each single non-concept branch, and `background=DominantColor`. Each other combination gives no output that its partial combinations do not give on the task or witness inputs.
- `$AreaRectangle` has a relational form. A candidate rectangle is the bounding box of the lock together with one cell of the lock's slab on the key's side. Two `Tally` counts compare the rectangle's cells with the pair's cells, so the rule needs no division.
- Undefinedness is gated per case through `defined`. Each of these makes the case undefined: two split colors or a color with three pieces (`$OnePairColor`), a crowded color (`$EveryPairColor`), a plugged color with no mover, and a plugged pair with no unique fit or no area rectangle.
- Lint hints: `common-subexpr` on `crowded` and `cand_pair` was resolved by factoring `piece_pair`. `single-consumer` on `rect` was resolved by inlining it. `negated-use` on `has_placement` was resolved by negating `placed`.
- The Determine comp was dropped. The first `determination-plan` asked for a determination relation for `background`. The relation I wrote kept the colors that every changed cell takes or leaves. The lint then said that its test reads the inputs and the outputs together, which is a guess-and-test determination and not a permitted clause form. Nothing in the concept gives `background` from one side alone, so the proposer and the fit enumeration determine it.
- `deletions` kept 28 removals that change nothing on the pairs. These removals are the undefinedness gates (`crowded`, `rival`, `ambiguous`, `unresolved`, `colors_defined`), the Interlock union box, and per-pair key columns. The witness inputs exercise these, or they keep the model total on inputs with several pairs, so they stay. The `Tally` `domain` rules were removed, because every key has members. The redundant `ex_out` atom in `off_change` was removed, and later the Determine comp that held it was dropped.
- Performance: every run took 2 s or less, and `deletions` took 20 s.
- Keywords: `objects move pack`.

## Unsettled
- `determination-plan` still lists `background (DominantColor exact)` and `mover_side (enumerable(4), pairs-exact)` after 3 runs. Settling it needs a determination of `background` from a fact of the inputs alone or of the outputs alone that the concept gives.
- `deletions` ran once, before the last edits. Those edits removed the Determine comp and inlined `rect`, and the pairs and witness runs after them pass. A run of `deletions` on the final file would settle whether any further removal changes nothing.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
