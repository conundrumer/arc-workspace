# beb8660c

## Departures
- The witness file's groups name `$Stack`, `$Bar & $Stack` and `$Ranked` where the Analyze file names `concept` with other branches: `record --all` rewrote each group to the fewest names over the witnessed cases, and the outputs are the Analyze file's on every witness.
- `$KeepOrder` has no constructor: the Analyze report gives it no witness, because it fails Fit at every pair.

## Judgments
- The concept's bar is a 4-connected `Components` run keyed by `[row, color]`, so the program's bar is a contiguous one-color run on one row, as `bars` states.
- One packing order serves both items: a unit's cell lands at its rank among the unit's cells from `align_side`. For a contiguous bar, that rank gives the bar's translation to the `align_side` edge. For `$RowUnit`, it gives the packing in order that the Analyze report states.
- `$RowByLength` lands a unit as many rows from `fall_dir` as its row has cells outside the unit, which is width − length without arithmetic.
- `$BaseStays` takes the base unit as a unit that holds `base_color`. For `$RowUnit`, that is a row that holds a `base_color` cell. With no base unit, the case is undefined. With two base units, both land on the edge row and conflict.
- `undefined` also covers a unit that lands past the frame, as the Analyze report gives for `$RowByLength`. It applies to every case.
- head-zero hint on `placed`: kept, with `@ignore`. The `0` is the base unit's distance from the `fall_dir` edge, so it counts no gap.
- negated-use finding: `has_base` is dropped, and `!base_unit(I, _)` replaces it.
- common-subexpr hint: `fall_dist` now serves both `undefined` and `landed`.
- Deletions:
    - `ink` in `rows.value` and `length.domain` changed nothing, so both are removed.
    - The `undefined` rules, the `$BaseStays` negations and the `$RowByLength & $BaseStays` clauses stay. They act only on inputs outside the pairs, or in cases that are not witnessed.
- Determination plan: `base_color` gets `Determine.base_color`, the color of the input row on the `fall_dir` edge, from the `base-bar` claim. `UnchangedColor` covers it from a different fact.
- No determination relation for `bg`: the concept stores `bg` and does not derive it from any fact of the evidence, and `DominantColor` gives the stored value over the examples. This is a judgment on the plan's wording.
- No determination relation for `fall_dir` and `align_side`: the train pairs fix each one in its enumerated domain (pairs-exact).
- The solver has 8 cases (every combination fits), and 4 of them are witnessed. The combinations are not witnessed, because every branch's verdicts are all `concept`.
- `derive` found no built-in derivation that fits, and `store` reported none.

## Open
- `distinct-colors` is left out of the header: no claim, branch or witness reads it, because bars are keyed by row and color. Should a later pass key bars by color alone, it would need that claim again.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
