# ba1aa698

## Departures
- The solver has a fourth branch at `uneven-steps`, `$SteadyChange`, with the witness `steady-change` (`foreign any`, `@relaxed constant-step`) (create). Develop step 3 forms it from the Not formed item "a step that changes by a constant amount", which states one model: the step changes by the same offset from each pair of panels to the next, and the next panel takes the last step changed once more. It fits every pair, because each pair's change is `ZERO`. On `steady-change` (steps of 1, 2 and 3 rows) it moves the shape 4 rows, `$LastStep` 3 and `$FirstStep` 1. This pass judged it to hold: its cases `$Step2D & $SteadyChange & $ClipAtEdge` and `$Step2D & $SteadyChange & $WrapAround` fit every pair, and `diagonal-uneven-past-edge` shows each defined and differing from every other case.
- On `uneven-steps`, `$SteadyChange` gives a grid, because the steps 3 and 1 differ by 2 rows, so the shape moves up one row. That witness's `separates` text names `$SteadyChange` (create).
- `impl_choice` holds 7 cases: the concept case, and the six cases that take `$Step2D`, one of `$LastStep`, `$FirstStep` or `$SteadyChange`, and one of `$ClipAtEdge` or `$WrapAround`. The Analyze report gives four such cases, and the two with `$SteadyChange` follow from the departure above. Each other combination fails Subsumption: it is defined only where one of the six is, and gives that case's output there. `witness --every-case` shows each single-branch case failing Subsumption, `$Step2D` against `$Step2D & $ClipAtEdge` and each other branch against its three-branch case. This replaces create's 24 combinations, which Write gives before Witness resolves Subsumption.
- Analyze-file run: the names `$Step2D`, `$LastStep`, `$FirstStep`, `$ClipAtEdge` and `$WrapAround` now denote models that are no cases, so the run checks no grid for them. A copy of the Analyze file, recorded again against the solver, gives each Analyze grid to the same branch, and adds the `$SteadyChange` grid on `uneven-steps`. A case that takes `$LastStep` also takes `$Step2D`, so on `diagonal-step` it gives the `$Step2D` grid, where the Analyze file gives the model of `$LastStep` alone as undefined. That model is subsumed and no case, so the Analyze file does not err.

## Judgments
- Reconcile: the brief gives no override. No other task's report has a `## Fixes elsewhere` item on this task. The solver passes every pair with lint ok, and the audit is ok in every section.
- Create's open item, that no combination case was witnessed, is settled by the new witness `diagonal-uneven-past-edge`. The shape steps one column along the row and 1, 2 and then 3 rows down, and one more step takes its right cell past the panel's right edge. Every case that takes part of a three-branch case's non-concept branches is undefined on it, and the six three-branch cases give six different grids. Plausibility `foreign`, because it breaks `constant-step`, `across-only` and `next-fits`, and the generator never draws uneven steps. Verdict `any`. It is a witness of combination cases and no branch's witness, so no `@witness` line records it.
- The enumerators `step_axes_choice`, `uneven_steps_choice` and `past_edge_choice` are removed. `step_at` reads `impl_choice([S, U, _])`, so the step relations range over the cases alone. A comment above `impl_choice` states which combinations are cases.
- Parse: the solver follows the approved precedent 135a2760 (create). Lines all of one color (`Unanimous<Line, Color>`) are the dividers of a `DividerTiles`. The interior of each panel is a `Bbox` of its tile cells. The bordered panel is a `Bbox` of the cells next to a tile cell, and it is the output's frame.
- The background is the commonest color inside the panels (`Mode`). A shape cell is a panel cell of another color (create).
- `induce`: the task is a nested task in sequence form (create). Each consecutive pair of panels is a demonstrated pair, and the answer is the panel after the last one. The catalog is `Translate {}`.
    - The predictions vary with all three `Choice` fields, so the `DemonstrationConsistency` instance is keyed by `Choice`.
    - `DemonstratedRule`'s `task` is therefore the case, and `out` carries `@ignore: head-repeat`.
- A panel that has a next panel is moved by its own step to that panel, so the catalog confirms one claim: each panel's content is the previous panel's shape moved rigidly over the background (`one-shape-per-panel`) (create). Only the step of the last panel depends on the branch: `$EvenSteps` reads the unanimous step (`constant-step`), `$LastStep` the step into the last panel, `$FirstStep` the first step, and `$SteadyChange` the last step plus the unanimous change.
- `$AcrossOnly` admits a pair's step only when the step has no component along the row axis, so a move along the row on any pair leaves the case undefined (create).
- `$WrapAround` walks each line of the interior as a cycle (`CycleWalk`), once per axis of the step, as "A wraparound shift is a walk around a cycle" gives (create). The walk is keyed by `[s, u, d]`, because the step counts vary by case.
- `$SteadyChange`'s witness: plausibility `foreign`, verdict `any`, on the same ground the Analyze report gives for `uneven-steps` (create).
- Not formed (create):
    - `extend-dir` from the input gives no derivation rule, so it states no model.
    - A shape that bounces back states more than one model: each cell mirrored at the edge, the step reversed, or the shape's box reflected.
    - A shape that changes between panels, and content that stays in place, have no reading.
    - An output of the interior without its border fails Fit at every pair.
- `derive`: no built-in derivation fits (create).
- `store`: it prints `change.item` and `change.value` as `no witness` lines with no line to add, and the Analyze report gives them no witness, so no `@store` branch is held (create).
- Determine: `sweep` gives `extend_dir` only DIR_R, and the plan gives it as pairs-exact over an enumerable domain with no proposer, so the solver has no `Determine` comp (create). The plan run by this pass gives the same.
- Lint hints: `interior` is a lib name, so the instance is `panel_box`; `same_line` replaces two `split` atoms; `panel_cell` carries the grid cell for `common-subexpr`; `head-repeat` is kept, as above (create).
- Deletions, run again over the changed solver:
    - `panels.tile_of` in `field.item` stays: the background is the commonest color inside the panels, and where the panels are narrow the divider lines can outnumber it.
    - The other removals that change no pair cut claims the pairs do not exercise: the demonstrations and their confirmation, the along-row test, the last-panel selection of each step, `leaves`, the clip test and the wrap cycle. They stay (create).
    - The removable `t` columns of `placed`, `drawn`, `leaves` and `wrap_axis` name the panel whose step applies, so they stay (create, with `drawn` added by this pass).
    - The bound enumerator `axis_elem(A)` in the `$WrapAround` `placed` clause stays, as the run says.
- Performance: no issue. A run takes about 1 s, the audit about 7 s, and `deletions` about 8 s.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-541_task_ba1aa698_refine.md
- 10-542_task_ba1aa698_refine.md
