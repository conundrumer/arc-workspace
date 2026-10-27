# cad67732

## Departures
- The witness file adds the witness `short-anti-shift-field`, which is not in `witnesses.json`: no Analyze witness showed the case `$LeastPeriodDiagonal & background=DominantColor` giving an output that no case with only part of its branches gives. The new input is the input of `short-anti-shift` on a field of 5, and each of the four cases gives its own output there. All four cases are now witnessed.
- `record --all` rewrote the witness file's group names into the forms the runner lists (`$CornerDiagonal & background=stored`, `$LeastPeriodDiagonal & background=stored`, and the others). The grids of the `witnesses.json` witnesses are unchanged, and `witness --file programs/reports/cad67732/witnesses.json` is ok.

## Judgments
- Constructors: `CornerDiagonal`, a name of my own, is the concept branch of `band diagonal`, and `LeastPeriodDiagonal` is the branch with the `analyze.md` name. `$StoredDiagonal`, `$StoredPeriod` and `$StoredCorner` have no constructor: `analyze.md` gives them no witness, and each fails Fit. `store` printed no line to add, because the diagonal and the period vary by input.
- Dropped branches: `$StoredDiagonal`, `$StoredPeriod`, `$StoredCorner`, `background=SharedColor` and `scale=ScaleRatio` fail Fit, for the reasons `analyze.md` gives. No item under Not formed states a model that meets Fit and is not equivalent to a case, so Develop step 3 formed no branch.
- `@derive DominantColor: variant derived` with `@relaxed diagonal-band` follows the `analyze.md` judgment of the witness `background=DominantColor`.
- `@witness short-anti-shift: variant concept` has no `@relaxed` line: the input breaks no scene claim of the header. The invariant it breaks, at least two whole periods in each input, is in no header claim. Its verdict is `concept`, so the `ordinary` check does not apply.
- Witness `anchor-edge`: plausibility `ordinary`, verdict `concept`. The input breaks no scene claim, and train1 already shows a band length that is not a whole number of periods. The concept's output there is the two grids of its open values, and the pairs do not decide between them.
- Witness `short-anti-shift-field`: plausibility `variant`, verdict `background=DominantColor`. A color-permuted variant task has a background other than 0, which breaks `diagonal-band` at the stored `background`. On that background the generator continues the band down the main diagonal on the field color.
- `continue-band`: `S <= T` on the distances to the anchor edge states "back toward the anchored input". When both cells are on one line along the band, this agrees with `!nearer(C, Q, P)`. The negated `nearer` crashed the run (see Tickets filed).
- Candidate periods are the nonzero distances of input cells to an edge. These are the shifts that can take a cell onto another cell of the input. `Extremes` gives the least one with no mismatch.
- Hint `reserved name` on `band`: renamed `band_axis`.
- Hint `determine prediction` on a first `scale` determination, which kept candidates by testing inputs and outputs together. The final `scale` reads the count of input-sized tiles that `divide_by_size` cuts from each train output. `background` keeps each color that is the commonest of every input, a fact of the inputs alone. `anchor_edge` is undecided, and the plan asks for no relation for it.
- Deletions that change nothing: `params.anchor_edge(E)`, `placed.e` and `reach.e` stay, because the witness `anchor-edge` separates the open values. The `inked_diagonal` atoms and `!inked_diagonal(DA2)` stay, because they make the concept undefined when both diagonals have colored corners, as the witness `background=DominantColor` shows. `background_defect` stays as the test that every input agrees, which the pairs never violate.
- Performance: no issue. Each run took a few seconds.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 17-33_task_cad67732_create.md
