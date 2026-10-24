# f15e1fac

## Concept
- Fits every pair (`work/task/f15e1fac/check_concept.py`, `work/task/f15e1fac/probe.py`). Every claim has a relational form: a ray cell's sideways offset is the sum of the steps of the markers whose lines lie between the seed edge and that cell's line, the marker's line included. No witness has verdict `other`, so the concept case has nothing to list. The rule as the generator applies it is the rule the concept file states.
- The one fitting alternative, `$SharedHeading`, agrees with the concept wherever it is defined, so it is subsumed. The pairs fix every other property: the heading, where the kink starts, its shape, the off-grid behavior, the step, and both colors.

## Choice points
- `kink heading`
    - `concept`: each marker steps the rays away from its own edge (`kink-at-marker`)
    - `$SharedHeading`: replaces `kink-at-marker`; one heading for every kink, away from the marker edge taken as a whole; no parameters; undefined on an input whose markers lie on both edges perpendicular to the seed edge. Fits every pair, and fails Subsumption since the concept gives its output wherever it is defined. Witness `markers-on-two-edges` (markers at row 3 on the left and row 6 on the right), at the stored assignment: it breaks `markers-on-adjacent-edge` and the invariant that every input's markers lie on one edge; plausibility `borderline`, verdict `concept`.
    - `$TowardMarker`: replaces `kink-at-marker`; the rays step toward the marker's edge; no parameters. Fails Fit at train0, where it steps left at row 4 and the output steps right.
    - `$StoredHeading`: replaces `kink-at-marker`; a stored direction for every kink. Fails Fit: train0 steps right, train1 left and train2 up, so no value fits every train pair.
    - `$TurnSense`: replaces `kink-at-marker`; the kink turns from the ray's heading in a stored sense. Fails Fit: train0 (heading down, step right) and train1 (heading down, step left) need opposite senses.
- `kink start`
    - `concept`: the marker's own line is the first line of the stepped segment
    - `$AfterMarker`: replaces `kink-at-marker`; the step starts on the line after the marker's. Fails Fit at train0, row 4 (output has `8` at cols 2, 6, 8, 10).
- `kink amount`
    - `concept`: every marker steps the rays `step` cells
    - `$GrowingStep`: replaces `kink-at-marker`; the k-th marker from the seed edge steps the rays k·`step` cells. Fails Fit at train0, rows 10–16, where the seed at col 9 would land at col 12, off the grid, and the output has it at col 11.
- `kink shape`
    - `concept`: the step is a sideways jump, with no cell joining the two segments
    - `$ConnectedStep`: adds a joining cell at the old offset on the marker's line. Fails Fit at train0, input (4,1), where the output has `0`.
- `off-grid`
    - `concept`: the part of a ray that steps off the grid is dropped (`clip-off-grid`)
    - `$Wrap`: replaces `clip-off-grid`; the offset wraps around the grid. Fails Fit at train1, (12,9) and (13,9), where the output has `0`.
    - `$PinAtEdge`: replaces `clip-off-grid`; a ray stays on the last line before the edge. Fails Fit at train1, rows 11–13, col 0, where the output has `0`.
- `seed_color`
    - `concept`: stored, 8
    - `seed_color=RarestColor`: replaces the stored `seed_color` with the color with the fewest cells in the input. Fails Fit at train0, where the rarest color is 2.
- `marker_color`
    - `concept`: stored, 2
    - `marker_color=RarestColor`: replaces the stored `marker_color` with the color with the fewest cells in the input. Fails Fit at train1, where the rarest color is 8.
- `kink heading` & `kink start`, `kink heading` & `kink amount`, `kink heading` & `kink shape`, `kink heading` & `off-grid`, `kink heading` & `seed_color`, `kink heading` & `marker_color`, `kink start` & `kink amount`, `kink start` & `kink shape`, `kink start` & `off-grid`, `kink start` & `seed_color`, `kink start` & `marker_color`, `kink amount` & `kink shape`, `kink amount` & `off-grid`, `kink amount` & `seed_color`, `kink amount` & `marker_color`, `kink shape` & `off-grid`, `kink shape` & `seed_color`, `kink shape` & `marker_color`, `off-grid` & `seed_color`, `off-grid` & `marker_color`, `seed_color` & `marker_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A ray that ends where it would step off the grid: its model is the concept's, since what it drops lies off the grid.
- `seed_color` or `marker_color` derived by SharedColor, DominantColor or the output-reading proposers (UnchangedColor, ChangedColor, OutNewColor, AnyOutNewColor, VanishedColor, ChangedPairs, VanishedNewPairs): SharedColor gives 0, 2 and 8 on every input and DominantColor gives the background 0, so no seed or marker set results. The output-reading proposers give nothing under `@derive`, so these models are undefined on every pair.
- Telling seeds from markers by count or by position instead of color: train0 has 4 seeds and 2 markers, train1 has 2 seeds and 3 markers, and the two sets sit alike on perpendicular edges, so nothing but color separates them.
- `step` derived: no proposer gives 1 on every input.
- `background` as a parameter the program reads: the program keeps the input and paints the rays, so it reads no background (scene parameter).

## Tickets filed
- none
