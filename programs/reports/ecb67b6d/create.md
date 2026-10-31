# ecb67b6d

## Departures
- The witness file renames the group `concept` of witness `mark_color=RarestColor` to `mark_color=stored`: the solver has a `@derive` branch on `mark_color`, so `concept` names the concept base, and that base holds both the stored and the derived case. `record --all` wrote the new name.

## Judgments
- The solver has one `Choice`-free base and a `@derive RarestColor` line on `mark_color`, so it has two witnessed cases: in `analyze.md`, every other branch (`$RunFourComps`, `$RunCellsOnly`, `$RunOneAxis`, `$RunAnyLine`, `$PureDiagonalRun`, `$ExactRun`) fails Fit and has no witness. So none of them is a constructor.
- `@derive RarestColor: borderline concept`, `@relaxed marks-on-field`: this takes the plausibility and the verdict of the `mark_color=RarestColor` witness in `analyze.md`. `derive` listed only this one derivation, and `store` had no findings.
- None of the Not formed items in `analyze.md` states a model that fits, so Develop step 3 added no branch.
- Run length: `Ray` casts from each mark cell toward each corner, and the casts stop at the first non-mark cell. `Tally` counts the cells of each cast, the source included. A clump recolors when one of its casts holds at least `min_run` cells. This is a comparison of a size against a bound, so it is not arithmetic. All four `DiagDir` values are cast, so the program has no orientation of its own.
- The run type `Cast` is a record inside `Parse<Key>`, as `.type Obj` is in the `Parse` of 00dbd492. With it, `Tally` can count per key, per source and per corner.
- Determine: `determination-plan` asked for a determination relation for `fill_color` (AnyOutNewColor), `mark_color` (RarestColor) and `min_run` (TileCount narrowed). `mark_color` and `fill_color` read the input and output colors of the changed cells. `min_run` keeps each run length of a recolored clump at which no kept clump reaches the threshold and every recolored clump reaches it. Only examples that have outputs are read. The second plan run gave no actions.
- `deletions`: `diag_dir_elem(D)` in `run_size.item` stays, because the narrowing idiom needs it (`Dir8` to `DiagDir`). The redundant `parse.clump.label` in `defect` is gone. I also removed `recolored(E, Id)` in `cand`, but that removal made a determine-prediction hint fire on `min_run` (a guessed value kept by a test that reads inputs and outputs together). So I put that atom back, and with the atom the candidates come from the evidence and lint is clean.

## Unsettled
- `deletions` ran once, before the last two edits: the removal of `parse.clump.label` from `defect`, and the restore of `recolored` in `cand`. A `deletions` run on the final file would settle whether any other atom is now redundant. The final pairs run passes, and lint is clean.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
