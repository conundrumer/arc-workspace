# d06dbe63

## Departures
- `$SingleMarker` is not in the solver: after its constructor was written, `witness` reported "no run shows `$SingleMarker` defined and differing from `$AnyCount`", so it fails Subsumption (as `analyze.md` predicted). The `MarkerCount` field, the `two-markers` witness (which then separated nothing) and every `$SingleMarker` group are gone. The `$SingleMarker & $StopAtCell` combination, which `analyze.md` gives as `$SingleMarker`'s model, went with it.
- `stored-step` witness: `assign` was `step` as a stamp picture holding 5s. It is now `step_cell`, the facts of the `RIGID(step, …)` block, each D4 image of the same step (3 up, 1 right) as `[D4, Offset]`. Its `@reassigned` line names `step_cell`. Two things forced this. The stamp layout takes 1 for a member, not 5. And the relabeling audit found that a half turn of the stored `step` changes no output, so the step went into a `RIGID` block. The output is unchanged from `witnesses.json`.
- The concept branches' constructors use names of my own: `SharedLeg`, `SharedFirstAxis`, `Legs`, `AxisCorners`, `NonBg`, `PassCells`. `record --all` rewrote every group to the forms the witness file allows (for example `["$SharedLeg", "$StoredStep"]` in place of the `concept, …` lists).
- Witnesses added beyond `witnesses.json`: `bg=DominantColor` and `marker_color=RarestColor` (written by `derive`), and `rarest-marker` (built, see Judgments).
- `leg-lengths` and `arm-first-axis` are fields of the `Legs` constructor of `StepForm`, not top-level fields. `analyze.md` says both points "exist only with the concept branch of `step-form`", and Principles put a point under the branch its property exists with.

## Judgments
- Encoding: the steps of an arm are a `Propagation<Arm, Position>` walk from the marker. Each edge goes from a step's start to its end, the same form as 69889d6e and a3df8b1e. The cells of a leg are the span on one line, past the leg's start and up to its end (`same_line`, `nearer`), so no count needs a range. `painted` keeps cells on the grid and on background, which gives `clip` and `keep-rest`.
- Arms are keyed by `[StepForm, DiagDir, marker]` and shared across cases, since each case's version of an arm is the same. `painted` joins each case's own `arm_corner` and `marker` back in. The 7 `case section` hints are static over-approximations of that sharing. They are dismissed with `@ignore: case section` on `diag_axis`, `corners`, `marker_color`, `marker` and `arm_corner`.
- `$StopAtCell` is a filter, not a walk that halts. Every step is monotone toward its corner, so "the first non-background cell an arm reaches" is the arm's blocked cell nearest the marker. `cut` drops each cell `nearer` the corner than a blocked cell. Its output on `crossing-paths` matches `witnesses.json`.
- `$StoredStep`: the step's corner and its end cell are derived from the stored cells (`step_corner`, `short_of`), not stored, because they follow from the step (Redundant value). The arm toward a corner uses the C4 image of the `RIGID` step whose corner it is. Only rotations of the stored pose are unobservable; a reflection changes the step's handedness, as the branch's claim ("turned by the rotation") requires.
- `bg=DominantColor` is held as a branch, judged `variant derived` with `@relaxed one-marker`. Its witness is train0 on a field of 1, which breaks the field-of-0 scene claim. The generator draws the same staircase on any field.
- `marker_color=RarestColor` is held for the `$MarkerByColor` cases, judged `variant derived`. On its `$NonBg` cases it fails Equivalence, since `$NonBg` reads no `marker_color` (`@ignore: derive $NonBg`).
- `marker_color` derived by `DominantColor`, `SharedColor` or `VanishedColor` fails Fit at train0: each gives 0, which makes every background cell a marker, and the arms then cover the grid (run at `marker_color` 0). Each has an `@ignore: derive` line.
- Witness `rarest-marker` is built because `witness` reported that no witness separated `$MarkerByColor & marker_color=RarestColor` from the concept. The input is one 8 and two 3s: the derived branch draws from the 8 alone, and the concept draws from all three. Judged `variant concept`: it breaks `one-marker`, and every non-background cell is a marker under the concept. A further witness of a `@derive` branch takes no `@witness` line.
- `legs` and `step_next` have `@ignore: store`. They are grid geometry that reads no color, and are one value only because every input is 13×13. `store` printed no line to add for them.
- Determination: relations for `bg` (the commonest input color), `marker_color` (the non-background input color), `path_color` (the output color painted over background), `leg` (the run of path cells that leaves the marker) and `leg2` (the run across from that run's end).
    - `diag_axis` and `first_axis` are enumerated by fit (1 of 4 joint assignments), and `corner_first_axis`, `corners` and `step` are undecided; the plan asks no act for any of them.
    - The sweep's extra single-row changes are not open values and are not stored: rows of `corner_first_axis` for corners no arm climbs toward, and `step` rows that land on the next step's cells or the start.
- The marker reading in `Determine` (`first.mark`: a non-background input cell) repeats one literal pair from `marker($NonBg(), …)`. I judged it too small for a `Parse`.
- Simplify: removed `in(Q, _)` from `step_next` and `placed` (`painted` and `blocked` already test the grid), and the path-color tests in `Determine` (a `clear` cell past its mark is a path cell). `deletions` flags the remaining entries (branch structure that one-marker pairs never instantiate, and needed columns) as structure the pairs do not exercise; they stay.
- Performance: `cut` first unpacked an `Arm` record variable that it joined two atoms on (`A = [_, C, _]`). That lost the index, and the runner killed the 169-marker `bg=DominantColor` witness after about 20 s. `blocked` now carries the corner as a column, so no `@workaround` is needed. `store` took 178 s and the first audits passed 240 s. With 40 base cases the audit now finishes in 21 s.

## Unsettled
- Whether a frame-geometry relation such as `legs` or `step_next` is owed a `@store` branch: a stored table of it would fit this task, since every grid is 13×13, and would differ on frames of another size. No witness was built. What would settle it: a doc line, or a `store` that skips relations that read no input color.
- Why `derive` reports `marker_color=DominantColor`, `SharedColor` and `VanishedColor` as fitting. What would settle it: a doc line on how `derive` judges Fit for a parameter that only some bases read.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
