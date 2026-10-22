# bc93ec48

## Departures
- The witness file has no copy of the Analyze witness `background=DominantColor`. `derive` built its own witness with that id (train1 with 7 and 0 swapped), and that one is kept: Witness, "remove each witness of a `@derive` or `@store` branch that duplicates the one `derive` or `store` records for that branch".
- `$CornerD4` stays as a case, but the Analyze report drops it under Subsumption. At one assignment of both `corner_d4` and `corner_target`, the two models differ. The added witness `d4-left-right` (test0's input, `corner_d4` = `D4_LR`) shows `$CornerD4` swapping the shapes left to right, while `$CornerMap` and the concept move them clockwise. The `witness` procedure keeps a case that a run shows defined and differing from the others.
- The header has no `corner-cells` scene claim: no `@claim` or `@relaxed` denotes it, no rule text depends on it, and no branch replaces it (Style, Header).
- `record --all` rewrote each group of the witness file to the fewest names, for example `$Conn4` for the concept's group on `diagonal-touch`.

## Judgments
- `Choice` is a record with four fields: `Shape` (`Conn4`, `$Conn8`), `Pick` (`CornerCell`, `$EdgePair`), `Clash` (`Unresolved`, `$Precedence`) and `Step` (`SenseStep`, `$CornerD4`, `$CornerMap`). With the `@derive DominantColor` point, that gives 48 cases, and 7 of them are witnessed. Every witnessed case passes every pair.
- `precedence` stores the 24 orders of the corners as `precedence(v: Ident, c: DiagDir, r: number)`, with dense ranks that the program reads only by comparison (Patterns, "Stored total orders as dense ranks"). Each `v` is one open value in the `OpenValue` column. A clash is settled by the rank of the copy's source corner.
- Where copies of different colors cover one cell, the concept emits both colors there, so that case is undefined. `$EdgePair` is undefined where a corner holds two shapes: `ambiguous` removes every `out` fact of the case.
- The solver has no Determine comp. The plan's covered values each come from the fact the concept itself uses: `background` from the field color (`DominantColor exact`), and `sense` and `corner_d4` from fit on the pairs over their domains. The plan gives `corner_target` and `precedence` to the values at which the model fits every train pair. The sweep reports a unique value for each swept parameter.
- Witness `d4-left-right`: plausibility `ordinary`, verdict `$CornerD4`. A generator whose corner step is the left-right reflection would pair the swapped output. No `@witness` line records it, because it separates two non-concept branches.
- The `@relaxed background-field` line stands only under the `@derive` line. `shape-hugs-empty-corner` and `copies-overlap` break invariants that the concept file does not list as scene claims, so they have no `@relaxed` line.
- Not formed: no item states a model. The counterclockwise `sense` is a value, not a branch, and the other items give no value. `store` reports no findings.
- Lint hints `negated-use` (`!painted` ⇒ `!paint`) and `long-clause` were fixed. `painted` was removed.
- `deletions`: 10 deletions change nothing. These are `ambiguous` and its negations, which the pairs never trigger because no corner holds two shapes, and `covered`, because no pair has a clash. They stay. In Simplify, the first `copy` atom of `covered` was removed, because the `copy` atom in the `paint` clause already gives it. The bound enumerator `diag_dir_elem(C)` stays, as the report says.
- Keywords `objects permutation move rank`: the corner shapes move by a fixed cycle of the corners, and `$Precedence` ranks the corners.

## Open
- Whether `$CornerD4` leaves under Subsumption: a ruling on how the definition applies to models that read different parameters would settle it (ticket 10-579).
- Whether `sense` or `corner_d4` needs a determination relation: a clearer line in `determination-plan` would settle it (ticket 10-580).

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-579_task_bc93ec48_create.md
- 10-580_task_bc93ec48_create.md
