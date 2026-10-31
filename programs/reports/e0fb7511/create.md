# e0fb7511

## Departures
- The concept branch of `qualifying-test` is the constructor `$GroupSize`. The witness file keeps the name `concept` for it, which denotes the same base: the analyze file gives that branch no constructor name.
- The `mark=RarestColor` witness lists the group of the stored-`mark` cases as `mark=stored`. `record --all` wrote that name because the concept base, `$GroupSize`, also has a case that takes `mark=RarestColor`.
- `derive` wrote a witness `min_neighbors=TileDim` to the witness file, and the solver removes it. The solver records that derivation with `@ignore: derive TileDim` (see Judgments).

## Judgments
- `min_size=TileCount` and `min_neighbors=TileDim` fail Relational form, so each has an `@ignore: derive` line. `derive` reports both as derivations that fit, but they take a tile count or tile size from the 13×13 grid extent. The task cuts the grid into no tiles, so the number counts nothing the task has. Not formed in `analyze.md` also says that no proposer derives a component size.
- `mark=RarestColor` is held as a `@derive` branch, with plausibility `borderline` and verdict `concept`, and relaxes `field-with-marks`. This follows the analyze file and the `derive` output.
- `fill=OutNewColor` and `fill=AnyOutNewColor` fail Fit, and `mark=DominantColor`, `mark=SharedColor` and `mark=VanishedColor` also fail Fit. The audit's derive check confirms that no `@derive` line is missing.
- `$Adj8` fails Fit at train0, and `$SizeTable` fails Fit at test0 (unseen keys 4 and 7). The analyze file gives neither branch a witness, so neither is a constructor.
- No item under Not formed states a model that fits and has a relational form, so Develop step 3 adds no branch.
- `store` reports only `neighbors.tally`. It varies by key and has no case, so the solver has no `@store` line.
- `deletions` reports that removing `neighbors.domain` changes nothing on the pairs. The rule stays. Without it, a mark cell with no mark neighbor gets no tally, and so the model at `min_neighbors` 0 would change.
- The determination plan asked for determination relations for `fill`, `mark`, `min_size` and `min_neighbors`. `Determine` reads `mark` and `fill` from the cells that the outputs change. It reads `min_size` and `min_neighbors` as the least group size and the least mark-neighbor count among the changed cells. The second plan run lists no actions.
- The group and neighbor parse is in `Parse`, which the program and `Determine` share.
- `witness` (with and without `--file`) and the final audit report no findings. Every pairs run passes, and the lint is clean.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
