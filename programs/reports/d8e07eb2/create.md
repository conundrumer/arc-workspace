# d8e07eb2

## Departures
- `divider_color=stored` is a constructor, `$StoredDivider` of `DividerColor`, with `params.divider_color(6)`. Its witness is renamed `stored-divider`: `run_dl.py store` printed "one color on every input: 6; make it a parameter" for `divider_color` and gave no `@store` line, so no store directive could record the branch.
- `key_side=stored` is a constructor, `$StoredSide {paint: StatusPaint}` of `KeySide`, with `params.key_side(DIR_T)`. Its witness is renamed `stored-side`, and the derived key side has `@ignore: store`. The reason: `analyze.md` puts `status-paint` under `key_side=stored`, and `witness` reported that no witness separates `$WholeStatus` from `$PaintBackground` under the derived key side. A choice point that stands under a branch needs that branch to be a constructor.
- `$IgnoreColor & $UpToD4` is left out of `impl_choice`. It fails Fit at train0–3 and test1, because ignoring color while matching up to D4 calls the 5 slot, a mirror image of the key's 6 shape. `analyze.md` gives the pair "the two branches' changes applied together", and that combination does not fit.
- On `background=DominantColor`, `$HaloTilingCell` is undefined, where `witnesses.json` gives it the concept's grid. The card there has one band on each axis, so it has no gap between bands. The branch's own text makes it undefined in that case, so `witnesses.json` erred.
- On `key_side=stored`, `card_slots=stored` wins and rings card row 1, where `witnesses.json` gives a losing grid. In the solver the key slots take their columns from `in_band`, which reads the stored card slots. The model in `witnesses.json` read them some other way. The witness file keeps the solver's grid.
- Key slots are the key band crossed with the card's column bands (`key_slot` reads `in_band`), as the `key` scene claim states. At first they crossed every column band, the key's own included. That was a bug, not a branch.
- `whole-status` had to be recorded with a different grid under `$WholeStatus`, because `$WholeStatus` now exists only under `$StoredSide`. Under the derived key side, both status-paint readings are undefined on that input.

## Judgments
- `background-swap` (built): train0 with colors 8 and 4 swapped. It is a color permutation of a train input, so it is a variant input. Plausibility `variant`, verdict `background=DominantColor`. Under that verdict the background is 4 and the card wins; with the stored background 8, the 4 lines are extra dividers and the model is undefined. The `@derive` line keeps the plausibility and verdict from `analyze.md` (`foreign concept`, witness `background=DominantColor`).
- `full-key-row` (built): train0 with row 0 painted 5. It resolves the finding that no run showed `$StoredDivider` defined and differing. Plausibility `borderline`, because no input has a second full line of a color that is neither background nor the divider. Verdict `$StoredDivider`: a reader keeps the 6 lines as the dividers.
- I kept three `@store` lines, on `slot_bands` and `card_slots` (the branches that `analyze.md` witnesses) and, before the key-side redesign, on `key_side`. The other ten relations that `store` listed carry `@workaround` lines. With all thirteen stored, `store` ran past 900 s and a plain run past 230 s, because each store point doubles the cases a run enumerates.
- Hints, judged and resolved:
    - single-consumer `divider_color`: gone after the Parse restructure.
    - pass-through `shape_cell`: folded into `framed`.
    - argmax `farther`: replaced by `Extremes<LineSide>`.
    - common-subexpr on `paint`, and later on `runs.node`: merged into disjunctions.
    - case-section and choice-tag findings: fixed by moving clauses under case markers and using `G != ...` tag variables.
- Determine: the sweep reported every parameter unique, and the plan listed actions for all six. I wrote a determination relation for each, and the plan then reported "no actions".
- Keywords: `decompose objects match lines bbox classify congruent`. `congruent` is claimed only by the `$UpToD4` case. `classify` is weak: the bingo or no-bingo bar is the class rendered. A later pass may drop it.

## Unsettled
- The pass was stopped at about 110 minutes by coordinator override. Last results, with their commands:
    - `uv run python scripts/run_dl.py d8e07eb2`: all 7 pairs PASS (15 witnessed cases), lint ok, determination ok.
    - `uv run python scripts/run_dl.py witness d8e07eb2`: `witness: ok`.
    - `uv run python scripts/run_dl.py record d8e07eb2 --all`: all 16 witnesses re-recorded.
    - `uv run python scripts/run_dl.py witness d8e07eb2 --file programs/reports/d8e07eb2/witnesses.json`: names `key_side=stored` and `divider_color=stored` that the solver no longer has, the `$HaloTilingCell` difference on `background=DominantColor`, and the `card_slots=stored` difference on `key_side=stored` (all under Departures).
- The final audit was not run. The last `uv run python scripts/run_dl.py audit d8e07eb2` (2000 s) ran before the `$StoredDivider` keying, the `KeySide` redesign and the Determine comp. It reported unwitnessed branches, since fixed. It also reported `store` findings on the nine relations that now have `@workaround` lines, and the `whole-status`/`key_side` separation, since resolved by the redesign. Settled by running the audit again.
- `uv run python scripts/run_dl.py derive d8e07eb2` and `store` were not rerun after the redesign. `derive` last listed only `background=DominantColor`.
- Simplify (`run_dl.py deletions`) and Prune were not done. The comments and header have not been pruned.
- The ten stored-value branches under `@workaround` lines (`card_cell`, `status_cell`, `runs.node`, `slot`, `card_slot`, `in_band`, `key_slot`, `status_paint`, `banded`) are not cases. Settled by a runner that does not double the case count per store point, or by `@ignore: store` judgments of equivalence.
- The proposer branch for `divider_color` is open: `determination-plan` reported `UnchangedColor narrowed(8)`, but `derive` listed no derivation for `divider_color`.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
