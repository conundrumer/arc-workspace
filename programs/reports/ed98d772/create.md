# ed98d772

## Departures
- `$StoredFrame` is the `@store` branch on `side`. Its name in the witness file is `side=stored`, and its witness id is `side=stored`: [Develop](#develop) step 4 holds a stored interpretation of a derived value that `analyze.md` gives a witness, and [Witness file](#witness-file) names a `@store` branch `<rel>=stored`. The run with `--file programs/reports/ed98d772/witnesses.json` reports only that `$StoredFrame` names no case.
- `$StepProduct` stores `axis_step(a: Axis, d: D4)` (V: `D4_HT`, H: `D4_CC`) in place of `col_step` and `row_step`: the step is a payload over the axis ([Orientation](docs/handbook/principles.md#orientation), Payload). Two named parameters would make the program pick an axis for each name, which is a hidden orientation.
- `$StepProduct` gives the diagonal quadrant the composition of the two steps only where both orders of composition agree, and it is undefined elsewhere: a fixed order would not be equivariant under a diagonal reflection, which swaps the two axes. On this task's steps (two rotations) both orders give `D4_CW`. `deletions` reports that dropping either `d4_compose` atom changes no pair, and both atoms stay for that reason.
- `@scene one-mark-color` is left out of the header: no `@claim` or `@relaxed` line refers to it, no rule text depends on it, and no branch replaces it ([Header](#header) style).
- Added witness `turn-sense` (train0's input, `turn_sense` reassigned to `SENSE_CW`): `witness` reported no witness separating `$SuccessiveTurns` from `$StepProduct`. Their clauses differ, and only a reassignment separates them. Judgment: plausibility `variant` (a clockwise pinwheel is a routine variant task), verdict `$SuccessiveTurns`. The generator turns that way, and the concept gives that output only with `quadrant_transform` reassigned too.
- Added witness `ring-4x4` (a 4×4 ring of 5 on 0): `witness` reported no run showing `side=stored` defined and different from `side=derived`. On that ring the four transforms agree where the 3-cell quadrants overlap, so `side=stored` gives a 7×7 grid and the concept gives 8×8. Judgment: plausibility `variant`, breaks `square-input` (n = 3), verdict `concept`. `side=stored` meets Subsumption and stays.

## Judgments
- Quadrants are boxes in the output frame: a box the input's size at each corner of a frame twice the input's side, from `edge_inset` at the opposite corner. `quadrant_transform` stays keyed by corner, as the concept states, with no 2×2 tile frame and no translation between corner and tile.
- `side` takes the input's extent only where both axes agree (`axis_dims(P, A, N, N)`), so every case that derives `side` is undefined on a non-square input, as `analyze.md` states.
- `$SuccessiveTurns` ranks the quadrant boxes with `LexOrder` (corner `order_corner`, axis `order_axis`) and gets rank `K` as `K` steps of a `CycleWalk` over D4, where one step composes one quarter turn in `turn_sense`. The walk starts at the identity, written `d4_compose(I, I, I)`, the one idempotent element, so no `D4_ID` literal is needed.
- `derive`: no built-in derivation fits, so there is no `@derive` line and no `@ignore: derive` line on `quadrant_transform`.
- `store`: it printed no line to add. `transform` is already stored as `quadrant_transform`. For `side` it printed "no witness", but `analyze.md` gives `$StoredFrame` a witness, so a hand-written `@store: variant concept` with `@relaxed square-input` stands on `side`, and it runs. No `@workaround` was added.
- Determination: `sweep` found every stored value unique. `determination-plan` (one run) listed `quadrant_transform` and `axis_step` as undecided, so the fit search over the train pairs determines them. A Determine relation for `quadrant_transform` that keeps each element no train pair contradicts drew the `determine prediction` hint, because it tests inputs and outputs together. That relation was removed, and the solver has no Determine comp. The four enumerated parameters are pairs-exact.
- Hint `common-subexpr` on the `$StepProduct` clauses: the one-step and diagonal clauses were merged into one disjunction.
- Lint `claim` on `turns`: `CycleWalk` has no `@construction` mark, so it got `@claim quadrant-copies`.
- `deletions`: `axis_elem(A)` in `side` and `d4_elem(T)` in `turns.succ` are bound enumerators, and they stay.
- Final state: every train pair and the test pair pass with 4 witnessed cases (concept, `$SuccessiveTurns`, `$StepProduct`, `side=stored`). Lint and audit are clean, and `witness` is ok.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
