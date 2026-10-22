# b6f77b65

## Departures
- `$FallToFloorEdge` is a constructor of a `Fall` choice point (`Choice` field `f`), and its concept branch is named `$StoredFall`: no built-in proposer derives a direction, and `derive` listed only `DominantColor` on `bg`. Its count of non-background cells per edge is `Tally` and `ArgExtremes`, and `fall_dir` sits under the `$StoredFall` marker in Params.
- The Analyze name `background=DominantColor` is `bg=DominantColor` in the witness file: the parameter is `bg`, and the name takes the `<param>=<Proposer>` form.
- The `@derive DominantColor` line records the witness `derive` built, `bg=DominantColor` (train 0 with 0 and 8 swapped), at `variant derived`, and does not record the Analyze judgment `borderline concept`. The Analyze witness `background=DominantColor` stays in the file as a further witness of that branch.
- On `structure-on-left-edge`, the concept, `$BarAtLowerTop` and `$BarToFoot` give a defined, scrambled grid at the stored `DIR_B`, where the Analyze file gives undefined. On `background=DominantColor`, `$FallToFloorEdge` (the left edge has the most `5` cells) and `bg=DominantColor` give defined grids, where the Analyze file gives undefined. The cause is the parse: the solver finds sticks cell by cell, so it finds some on any input. The probe's exact cover by arches finds none on those inputs. The `separates` texts of both witnesses now state the defined outputs.
- `record --all` rewrote the groups of every witness to list the combinations of branches, which the Analyze file left out.

## Judgments
- `bar-hangs` has a relational form, but `Gravity` cannot state it. A bar's hold is not monotone in its legs' travel: a leg that falls farther can turn a failed hold into one that stops the bar sooner. So `Gravity`'s recursion over upper bounds of travel would admit false bounds (on `far-leg-drops-past-near-foot` it would stop the bar at row 9 in place of the floor). The proposal comp `HangingGravity` instead computes each body's exact travel once every body it rests against has come to rest. The recursion is positive: a running minimum over the ranked bodies ahead, then a scan over travels that stops where every hang holds. The concept, `$BarAtLowerTop` and `$BarToFoot` differ only in the `hang` rows they give it.
- The parse is local, and it does not search for an exact cover. A stick cell with a stick cell or the frame edge past it toward the fall is a leg cell. A stick cell with background past it is a bar cell. The sticks are `Components` keyed by `[fall, axis, color]`, and a bar's legs are the legs beside its end cells. The parse rests on scene invariants: no two legs lie side by side, a leg's color differs from the stick it stands on, and the inside of an arch under its bar is empty.
- `leg_depth` keeps its `c` column, though `deletions` reported it removable on the pairs. With the column removed, a leg's depth was read from a cell beside another bar, and the concept's output on `structure-on-left-edge` changed.
- `deletions` also listed these, and they stay. The comp's `blocked` input keeps the interface of `Gravity`. `!params.bg` in `marker` and `!marker_line` in `stick_cell` state the scene. `!pulled` in `whole` keeps a pulled bar from taking a travel. The `_stop` disjunct of `_rest` gives the bar on `far-leg-drops-past-near-foot` its rest on the floor. These were removed: the hang bodies from `_dep`, `edge_tally.domain`, a redundant `fall` atom in `out`, and the line test in `$BarAtLowerTop`. `foot` was folded into its one use.
- `bg=DominantColor`: `variant`, since the witness is a color permutation of train 0. `derived`, since its background is 8. At the stored `bg` it breaks `marker` and `arches`.
- `// @ignore high: store`: the stored value of `floor_edge.high` under `$FallToFloorEdge` is the stored `fall_dir` of `$StoredFall`, so that case is equivalent to one with fewer non-concept branches and fails Equivalence. `store` gave `marker_line` no witness and no line to add, so no branch holds it.
- Not formed, each as a branch:
    - Clearing the marker cells with the sticks they name fails Fit on every pair, since each output keeps the marker.
    - Per-cell packing in each column fails Fit on train 4, where the `3 3 3` bar rests at row 8 above two empty cells.
    - The settling order gives no other model.
    - `marker_corner` gives no model, since no rule reads it.
- The case `$BarAtLowerTop & $BarToFoot` is a case of the solver and is not witnessed, because every verdict on both branches is `concept`.
- Keywords: `objects markers select move`.
- Determine: `sweep` reported each parameter unique, and `determination-plan` listed no actions. The solver has no Determine comp.

## Open
- The lint's `recursion` finding on `HangingGravity` stands: the comp has no entry under `docs/wf-solver/proposals/`, and this pass may not write one. The lib pass's entry would settle it.
- Whether the concept case should check the scene, for example that each bar has a leg at both ends, and be undefined where the arch parse fails, as the Analyze probe is: the reviewer's judgment settles it.

## Lib
- `HangingGravity<Key, Body>`, a primitive operation (recursion, aggregates, arithmetic). Rigid bodies fall toward one heading. Each body stops at the least travel that brings it against the frame edge, a blocked cell or another body at rest. A body that hangs stops sooner, at the least travel at which, for each body it hangs on, a `hang(key, b, b2, k)` row holds: `b` has travelled `k` cells farther than `b2`. Requires: no cycle of resting or hanging. Solver-local form: `programs/solvers/b6f77b65.dl`, `.comp HangingGravity`, instanced as `settle` and keyed by `Choice`. A grep of the `Gravity` solvers for hang, held and hold, and of all solvers for `hang`, found no other site.

## Fixes elsewhere
- none

## Tickets filed
- 10-387_task_b6f77b65_create.md
- 10-388_task_b6f77b65_create.md
