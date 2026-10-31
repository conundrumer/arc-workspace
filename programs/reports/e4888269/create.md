# e4888269

## Departures
- `$Legend8Adj` has no case, and the witness `diagonal-mark` is removed from the witness file. The witness file's `divider-source` group no longer names `$Legend8Adj`. `witness --file witnesses.json` reports that `$Legend8Adj` denotes no case of the solver on both witnesses: the branch fails Subsumption, as `analyze.md` states. The first encoding found the 8-connected legend without a shape check. That encoding was defined and different on a pair of same-colored marks that touch the legend at a corner (`3 3` at train0 (4,2), (4,3)): the pair joined the legend as an identity entry and kept its color. It also gave a second legend for two single-colored marks that touch at a corner. `analyze.md` defines the branch as undefined wherever a non-background cell touches the legend at a corner. Under that definition, the branch is defined only where every multi-colored 8-group is one solid two-wide block that no other non-background cell touches. There, that block is also the one multi-colored 4-group, so the legends are the same and so are the outputs. `diagonal-mark` then separates nothing.

## Judgments
- The solver has one choice point, `Choice` = `RecolorAll` (concept) | `KeepDivider`: `analyze.md` gives witnesses to `$Legend8Adj` and `$KeepDivider` only, and `$Legend8Adj` leaves under Subsumption. Every other branch fails Fit and has no witness.
- No branch comes from Not formed. Each item there is equivalent to the concept, fails Fit, or is a stored parameter value.
- `derive` finds no built-in derivation that fits, and `store` has no findings. The background is derived by `Mode` because test0's background is `1` and the others' is `0`.
- Sequential application is a walk through `Propagation<Unit, Visit>`, with nodes [start color, current color, entry]. `Order` gives `first`, `next` and `last` over the entries' source cells, ordered by `nearer(order_dir)`. This states each step's color change with no recursion in the solver.
- `Unanimous<Line, Color>` finds the divider lines. It is keyed by `[a: Axis, l: Position]`, where `l` is the axis-only part of the cell from `split`.
- Sweep: `order_dir` and `source_dir` are each unique at the stored values. The determination plan lists no proposer-derived values, so the solver has no Determine comp. Both values are determined as the values of their types at which the model fits every train pair.
- Deletions: `!legend(Q)` and `legend(T)` in `entry` imply each other on a two-wide block. `legend(T)` was removed. The `recolor(P, _)` gate on the divider clause of `$KeepDivider` was removed because it changes no output. The divider rules change no pair output because the pairs do not separate `$KeepDivider`, and `divider-source` separates it. The bound enumerator `axis_elem(A)` in `divider` stays, as the run directs.
- Keywords: `objects` (legend found as a component), `mapping`, `rank` (entry order), `walk` (each step reads the color the earlier steps leave), and `lines` (claimed by `$KeepDivider`).

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
