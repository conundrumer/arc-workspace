# e50d258f

## Departures
- The header leaves out the `patch-palette` scene claim: no `@claim` or `@relaxed` line refers to it, no rule text depends on it, and no branch replaces it (Style, Header).

## Judgments
- `$ExcessOverMark` compares patches pairwise with `Excess<Rival, Position>`. Patch x beats patch y when x's `count_color` cells together with y's `minus_color` cells outnumber y's `count_color` cells together with x's `minus_color` cells. The selected patch is the one that no other patch beats. Before this form, the solver used one `Excess` per patch and ranked the excesses with `ArgExtremes`. That form failed train 2 and test 0: `Excess` gives no tuple at a deficit, and in those inputs every patch has more `1` cells than `2` cells. The pairwise form needs no arithmetic and orders patches by the analyze.md score, negative scores included.
- `Components<Unit>` and `Components8<Unit>` are separate instances, joined in `patch(a, p, id)` under their `Adjacency` tag. The `step` input of `Components` takes no key, so one keyed instance cannot hold both adjacencies.
- The concept uses `Mode<Adjacency, Ident, Position>` over `count_color` cells, following ae4f1146.
- Not formed items: none of them states one model that meets Fit, so Develop step 3 added no branch. The largest patch, the smallest patch and the fewest `8` cells each fail train 0. The tiebreak and the edge-sharing split are not models. `count_color` as the mark color determines no value.
- `derive` reports that no built-in derivation fits. `RarestColor` and `DominantColor` (analyze.md) fail Fit at train 0. `store` reports no findings.
- `sweep` reports that the train pairs also admit `minus_color` = `0`. No reader takes the field color as the subtracted mark, and patches hold no `0` cell, so `0` makes `$ExcessOverMark` the same as the concept. That makes `0` no open value, and the solver keeps `1` alone.
- Determine: `bg` is the color that fills a whole row or column of every input. The first form was the input color that no train output holds. The plan rejected it because the `cell-in-patch-box` witness output holds `0`. The new form reads the inputs alone.
- `deletions`: the atom `patch(A, P, Id)` and the background branch of the `$CropOwnCells` clause change no pair output. This is because, under `rect-patches`, a patch's box holds only that patch's cells. The `cell-in-patch-box` witness shows that both are needed. `lacks` and `!lacks(C)` change no determined value, because no train input has a whole line of a non-field color. These clauses state the universal over inputs, so they stay.
- The last pairs run passes every pair with 4 witnessed cases. Lint, the determination check (`bg`) and the audit all pass.

## Unsettled
- `minus_color` determination: the plan lists it as `pairs-ambiguous(2)` (`0`, `1`), and the solver has no determination relation for it. A relation that keeps `1` from the inputs alone would settle it, for example the non-field color that is neither `count_color` nor the commonest patch color. I stopped at the cap of 3 plan runs.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
