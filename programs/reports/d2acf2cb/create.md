# d2acf2cb

## Departures
- The `one-axis` scene claim is left out of the header. No `@claim`, `@relaxed`, rule text or constructor refers to it. Its only branch, `$StoredAxis`, fails Fit and has no witness.
- The `$WithDiagonals & $OneEnd` combination is left out of `impl_choice`. It fails Fit on every pair: diagonals cast from single markers recode extra cells, for example train0 (0,3), (1,4), (0,5).
- Constructor names chosen for the concept branches: `$Straight` (line-family), `$EdgePair` (segment) and `$Strict` (unmapped). `record --all` rewrote the witness file's `concept` groups to those names.

## Judgments
- The `@ignore: head-repeat` on `recode`: under `$KeepUnmapped`, a color that is no key of `params.recolor` maps to itself, and that identity row is the claim.
- The `@ignore: store` on `recode`: `store` reported `recode` constant on every input for `$KeepUnmapped`. A stored table of those rows is a `params.recolor` with another value, read under `$Strict`, so its branch is the concept model and fails Equivalence.
- `derive` reported `marker=RarestColor` alone, and it is written as `@derive RarestColor: variant concept`, as analyze.md gives it. No derivation fits `recolor`.
- No item under Not formed states a model that fits, so Develop step 3 added no branch.
- Determine, `marker`: the first form read colors no train cell changes from, and the hint flagged it for keeping a guessed value by a test that reads inputs and outputs together. The second form used the pairing scene claim, and the plan showed it broke when lone-marker was added. The kept form reads the color of the two end cells of a row or column whose cells between them all change, and the plan reports no actions.
- Determine, `recolor`: it reads the changed cells' pairs.
- Other `deletions` items kept: the `impl_choice` atom in the recoded `out` clause keeps out the `out` facts of non-cases. The `$KeepUnmapped` rule never fires on the pairs, which hold no third color. The atoms of `inside` that locate the end cells state the concept's pairing. The `from_end.p` column was removed.
- The sweep showed 15 single-row changes of `recolor` that still fit; all of them add keys for colors no input holds. No reader of the concept takes them as open values, and none is stored.

## Unsettled
- Combinations such as `$WithDiagonals & $KeepUnmapped` have no witness of their own. `witness` reports no pair left unseparated, and an input with a third color on a marked diagonal would witness them.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
