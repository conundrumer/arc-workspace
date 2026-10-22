# ba1aa698

## Concept
- Fits every train pair and the test pair at `extend-dir` R (the probe `work/task/ba1aa698/probe.py` gives each pair's output exactly). Train 1 fits as its patch leaves it.
- `next-panel` has a relational form, so it approximates nothing, and no witness has the verdict `other`.
- The concept case is undefined where `across-only`, `constant-step` or `next-fits` breaks. Each choice point below adds a model that is defined on some of those inputs.

## Choice points
- `step-axes`: whether the shape's place along the panel row also steps
    - `concept`: `across-only`. The shape keeps one place along the row, and the concept is undefined where it moves along the row.
    - `$Step2D`: replaces `across-only`. The step is one offset on both axes, the same from each panel to the next, and the next panel's shape moves by it on both axes. Undefined where the offsets differ between steps. Fits every pair. Witness `diagonal-step`: breaks the scene claim `across-only` and the invariant of the inputs that the shape keeps its column in every panel. Plausibility `variant`, verdict `$Step2D`. Its single-branch case is subsumed by every case that takes it with `$LastStep` or `$FirstStep`.
- `uneven-steps`: the step that is read where the panels' steps differ
    - `concept`: `constant-step`. The concept is undefined where the steps differ.
    - `$LastStep`: replaces `constant-step`. The step is the move between the last two panels. Defined wherever two panels show the shape. Fits every pair. Witness `uneven-steps`: breaks the scene claim `constant-step` and the invariant of the inputs that all steps are equal. Plausibility `foreign`, verdict `any`. Its single-branch case is subsumed by every case that takes it with `$ClipAtEdge` or `$WrapAround`.
    - `$FirstStep`: replaces `constant-step`. The step is the move between the first two panels. Fits every pair. Witness `uneven-steps`, with the same scene claim, invariant, plausibility and verdict as for `$LastStep`. Its single-branch case is subsumed in the same way.
- `past-edge`: what is drawn where one more step takes shape cells past the panel's edge
    - `concept`: `next-fits`. The concept is undefined there.
    - `$ClipAtEdge`: replaces `next-fits`. The shape cells that land outside the panel are dropped, and an empty panel is drawn where none lands inside. Fits every pair. Witness `step-past-edge`: breaks the scene claim `next-fits` and the invariant of the inputs that the next place lies inside the panel. Plausibility `foreign`, verdict `any`. Its single-branch case is subsumed by every case that takes it with `$LastStep` or `$FirstStep`.
    - `$WrapAround`: replaces `next-fits`. A shape cell that lands outside the panel wraps to the opposite side, with each coordinate taken modulo the panel's extent on that axis. Fits every pair. Witness `step-past-edge`, with the same scene claim, invariant, plausibility and verdict as for `$ClipAtEdge`. Its single-branch case is subsumed in the same way.
- `step-axes` & `uneven-steps`, `step-axes` & `past-edge`, `uneven-steps` & `past-edge`: the two branches' changes applied together.
    - Every non-concept branch only makes the model defined on inputs where the concept is undefined. So the only cases that pass Subsumption are the concept case and the four cases that take `$Step2D`, one of `$LastStep` or `$FirstStep`, and one of `$ClipAtEdge` or `$WrapAround`.

## Open parameters
- none

## Not formed
- `extend-dir` derived from the input: no proposer gives a `Dir`, and nothing in the input tells the two ends of the panel row apart. The shape moves down in train 0 and train 1 and up in train 2, and the sequence continues past the right end in all three. The value L fails train 0, because it puts the shape at row 1 in place of row 6.
- A step that changes by a constant amount (an accelerating move): no pair, solver header, lib component or proposer gives it. The header of 351d6448 leaves its frames undefined where the steps differ.
- A shape that bounces back from the panel's edge: no pair, solver header, lib component or proposer gives it.
- A shape that changes between panels, or content that stays in place in every panel beside the moving shape: no pair shows either one, and `one-shape-per-panel` leaves the concept undefined there. No source gives a reading of them under this concept.
- An output that is the panel's interior without its border: every train output has the border of divider lines.

## Tickets filed
- none
