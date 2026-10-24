# d2acf2cb

## Departures
- `$BackgroundElse` has no constructor. It is now the second open value of `$ForegroundElse`'s `params.split` (`split(6, 7, 8)`, `split(0, 8, 7)`): analyze.md's two branches are one model with the parameters renamed. `fg`/`bg`, `fg_to`/`bg_to` and `other_to` range over the same colors, and colors have identity and nothing else, so every assignment of one has an agreeing assignment of the other. Kept as two cases, one of them would fail Equivalence. The pairs leave both assignments open: (6, 7, 8) and (0, 8, 7) fit every train pair, and the determination's `split` keeps both. Folding them into one `@open` relation gives the output M_open gives. In the witness file, `$BackgroundElse` is removed and third-color's `separates` text is rewritten. `$ForegroundElse` now gives two grids on third-color, 8 and 7 at (5,4), which are the grids analyze.md's two branches gave. This is the one difference `witness --file programs/reports/d2acf2cb/witnesses.json` prints, apart from the `$BackgroundElse` name.
- The branch keeps analyze.md's name `$ForegroundElse`, but it no longer picks out a foreground. Its `@rule` line says what it does: one color c of `params.split` takes c_to, and every other color takes other_to.
- The parameterization changed in Determine: three single-valued relations `fg`, `fg_to` and `other_to` became one `@open` relation, `split(c, c_to, other_to)`. The three separate relations could not be determined jointly, and three separate `@open` relations would have mixed values from different assignments. Develop was run again over the changed solver.
- The `one-axis` scene claim is left out of the header. No `@claim`, `@relaxed`, rule text or constructor refers to it. Its only branch, `$StoredAxis`, fails Fit and has no witness.
- The `$WithDiagonals & $OneEnd` combination is left out of `impl_choice`. It fails Fit on every pair: diagonals cast from single markers recode extra cells, for example train0 (0,3), (1,4), (0,5).
- Constructor names chosen for the concept branches: `$Straight` (line-family), `$EdgePair` (segment), `$Recolor` (recode) and `$Strict` (unmapped). `unmapped` is nested as the field of `Recolor`, because the property exists only with that branch. `record --all` rewrote the witness file's `concept` groups to those names.

## Judgments
- The `@ignore: head-repeat` on `recode`: under `$KeepUnmapped`, a color that is no key of `params.recolor` maps to itself, and that identity row is the claim.
- The `@ignore: store` on `recode`: `store` reported `recode` constant on every input for `$ForegroundElse` and for `$KeepUnmapped`. A stored table of those rows is a `params.recolor` with another value, read under `$Strict`, so its branch is the concept model and fails Equivalence.
- `derive` reported `marker=RarestColor` alone, and it is written as `@derive RarestColor: variant concept`, as analyze.md gives it. No derivation fits `recolor` or `split`.
- No item under Not formed states a model that fits, so Develop step 3 added no branch.
- Determine, `marker`: the first form read colors no train cell changes from, and the hint flagged it for keeping a guessed value by a test that reads inputs and outputs together. The second form used the pairing scene claim, and the plan showed it broke when lone-marker was added. The kept form reads the color of the two end cells of a row or column whose cells between them all change, and the plan reports no actions.
- Determine, `recolor` and `split`: both read the changed cells' pairs. `split_clash` states that every other color takes other_to. The pairs never instantiate it, because only two colors change, and `deletions` lists it; it stays because it states the claim.
- Other `deletions` items kept: the `impl_choice` atom in the recoded `out` clause keeps out the `out` facts of non-cases. The `$KeepUnmapped` rule never fires on the pairs, which hold no third color. The atoms of `inside` that locate the end cells state the concept's pairing. The `from_end.p` column was removed.
- The sweep showed 15 single-row changes of `recolor` that still fit; all of them add keys for colors no input holds. No reader of the concept takes them as open values, and none is stored.

## Unsettled
- Of the 9 cases, 6 are witnessed. Combinations such as `$WithDiagonals & $KeepUnmapped` have no witness of their own. `witness` reports no pair left unseparated, and an input with a third color on a marked diagonal would witness them.
- `$ForegroundElse` with two open values versus analyze.md's two branches: a reviewer should confirm that folding `$BackgroundElse` into open values, rather than keeping it as a separate case, is the intended reading of Equivalence.

## Concept faults
- none

## Fixes elsewhere
- programs/reports/d2acf2cb/analyze.md, the `$BackgroundElse` line under `recode`: it is the `$ForegroundElse` model with renamed parameters (equivalent models), so it is not a separate branch. The pairs leave two assignments of that one model open.

## Tickets filed
- none
