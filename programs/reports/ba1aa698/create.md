# ba1aa698

## Departures
- The solver has a fourth branch at `uneven-steps`, `$SteadyChange`, with the witness `steady-change` (`foreign any`, `@relaxed constant-step`). Develop step 3 forms it from the Not formed item "a step that changes by a constant amount", which states one model. In that model, the step changes by the same offset from each pair of panels to the next, and the next panel takes the last step changed once more. That model fits every pair, because each pair's change is `ZERO`. On `steady-change` (steps of 1, 2 and 3 rows), it moves the shape 4 rows, `$LastStep` moves it 3 and `$FirstStep` moves it 1.
- On `uneven-steps`, `$SteadyChange` gives a grid: the steps 3 and 1 differ by 2 rows, so the shape moves up one row. So that witness's `separates` text now names `$SteadyChange`.
- The Analyze report says that only the concept case and the four three-branch cases pass Subsumption. The solver holds all 24 combinations, as Write gives. The run witnesses 7 of them: the concept case and the case of each single branch. `witness` reports no case that no run shows defined and differing from another case, so no case leaves.

## Judgments
- Parse: the solver follows the approved precedent 135a2760. Lines all of one color (`Unanimous<Line, Color>`) are the dividers of a `DividerTiles`. The interior of each panel is a `Bbox` of its tile cells. The bordered panel is a `Bbox` of the cells next to a tile cell, and it is the output's frame.
- The background is the commonest color inside the panels (`Mode`). A shape cell is a panel cell of another color.
- `induce`: the task is a nested task in sequence form. Each consecutive pair of panels is a demonstrated pair, and the answer is the panel after the last one. The catalog is `Translate {}`.
    - The predictions vary with all three `Choice` fields, so the `DemonstrationConsistency` instance is keyed by `Choice`.
    - `DemonstratedRule`'s `task` is therefore the case, and `out` carries `@ignore: head-repeat`.
- A panel that has a next panel is moved by its own step to that panel. So the catalog confirms one claim: each panel's content is the previous panel's shape moved rigidly over the background (`one-shape-per-panel`). Only the step of the last panel depends on the branch: `$EvenSteps` reads the unanimous step (`constant-step`), `$LastStep` the step into the last panel, `$FirstStep` the first step, and `$SteadyChange` the last step plus the unanimous change.
- `$AcrossOnly` admits a pair's step only when the step has no component along the row axis. Thus a move along the row on any pair leaves the case undefined.
- `$WrapAround` walks each line of the interior as a cycle (`CycleWalk`), once per axis of the step, as "A wraparound shift is a walk around a cycle" gives. The walk is keyed by `[s, u, d]`, because the step counts vary by case. With a key of `Dir` alone, lint gave case-section hints, because cases read steps from the clauses of other cases.
- `$SteadyChange`'s witness: its plausibility is `foreign` and its verdict is `any`. The generator never draws uneven steps, which is the same ground the Analyze report gives for `uneven-steps`.
- Not formed:
    - `extend-dir` from the input gives no derivation rule, so it states no model.
    - A shape that bounces back states more than one model: each cell mirrored at the edge, the step reversed, or the shape's box reflected.
    - A shape that changes between panels, and content that stays in place, have no reading.
    - An output of the interior without its border fails Fit at every pair.
- `derive`: no built-in derivation fits.
- `store`: it prints `change.item` and `change.value` as single `no witness` lines, with no line to add, and the Analyze report gives them no witness. So no `@store` branch is held. A stored `ZERO` change would give `$LastStep`'s model.
- Determine: `sweep` gives `extend_dir` only DIR_R. The plan gives `extend_dir` as pairs-exact over an enumerable domain, and no proposer derives it. So the plan lists no determination relation to write, and the solver has no `Determine` comp.
- Lint hints:
    - `interior` is a lib name, so the instance is now `panel_box`.
    - The lib idiom `same_line` replaces two `split` atoms.
    - `common-subexpr`: `panel_cell` now carries the grid cell, and the prediction reads it.
    - `head-repeat` is kept, as above.
- Deletions:
    - These were dropped: `in(P, _)` in `framed.cell`, `panels.tile_of` in `shape` (`crop` already implies it), and `!leaves` in the `$InsidePanel` `placed` clause (`drawn` already guards the prediction).
    - The other removals that change nothing cut claims that the pairs do not exercise: the demonstrations and their confirmation, the along-row test, the last-panel selection of each step, `leaves`, the clip test and the wrap cycle. So they stay.
    - The removable `t` columns of `placed`, `leaves` and `wrap_axis` name the panel whose step applies, so they stay.
- Performance: no issue. A run takes about 1 s, and `store` takes about 12 s.

## Open
- None of the 17 combination cases is witnessed. The four three-branch cases, which the Analyze report gives as the cases that pass Subsumption, are among them. No input of the task or of the witness file shows a combination that gives an output no case with part of its branches gives. A witness whose shape steps diagonally, by uneven steps, and past the panel's edge would settle whether those cases stay, and whether the single-branch cases then fail Subsumption.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-539_task_ba1aa698_create.md
