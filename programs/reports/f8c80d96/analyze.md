# f8c80d96

## Concept
- Fits every pair: train0 step 2, train1 step 3, train2 step 2, test step 3 (`work/task/f8c80d96/check_concept.py`, `work/task/f8c80d96/probe.py`).
- No witness has verdict `other`. The rule as the generator applies it: the generator draws the whole nested family from the innermost outline outward until the grid edge, then hides the outer outlines. `grow-outward` draws the same outlines, because in every input the innermost outline is the last one that fits toward the open corner or edge.
- The concept case is defined only where the input has two or more nested outlines in one color and one step is shared by every side and every pair of consecutive outlines.

## Choice points
- `growth-direction`
    - `concept`: grow outward from the outermost outline only.
    - `$GrowInward`: adds `grow-inward`: also draws each outline the step gives inward from the innermost one, until the next one falls outside the grid or turns inside out. No parameters. Undefined where the concept is. Fits every pair. Witness `missing-inner-outline`: it breaks no scene claim and stands at the stored assignment. Plausibility `variant`, verdict `$GrowInward`. It breaks the invariant that in every input the innermost outline leaves no room for another one inside it at the step.
- `step-granularity`
    - `concept`: one step for every side (`uniform-step`).
    - `$PerAxisStep`: replaces `uniform-step` with one step per axis, each derived from the gaps on that axis. Undefined where the two sides of one axis step differently. Fits every pair, and fails Subsumption: on every input where it is defined, `$PerSideStep` gives the same output. Witness `unequal-axis-steps`: it breaks `uniform-step` and stands at the stored assignment. Plausibility `variant`, verdict `$PerAxisStep`. It breaks the invariant that the vertical and horizontal gaps are equal.
    - `$PerSideStep`: replaces `uniform-step` with one step per side, each derived from the gaps on that side. Undefined where one side's gaps differ between consecutive outlines. Fits every pair. Witness `unequal-side-steps`: it breaks `uniform-step` and stands at the stored assignment. Plausibility `borderline`, verdict `$PerSideStep`. It breaks the invariant that the two opposite sides of an outline move by the same step.
- `step-source`
    - `concept`: the step is derived from the gap between consecutive outlines.
    - `step=stored`: the step is a stored value, which replaces the derivation in `uniform-step`. Fails Fit at train1: train0 needs 2 and train1 needs 3.
- `stop-rule`
    - `concept`: keep growing up to the first outline that falls wholly outside the grid (`grow-outward`).
    - `$StoredOutlineCount`: replaces the stop in `grow-outward` with a stored count of added outlines. Fails Fit at train1: train0 adds 2, train1 adds 1, train2 adds 3.
- `line-color`
    - `concept`: derived as the input's one color other than `background` (`one-line-color`).
    - `line_color=stored`: fails Fit at train1: train0's line color is 8 and train1's is 1.
- `background`
    - `concept`: stored, 0.
    - `background=DominantColor`: derived as the commonest color of the input, and undefined where two colors tie. Fits every pair. Witness `background=DominantColor`, which is train0's output with 5 recolored 0: the 8 outlines already fill the grid and outnumber the 0 cells. It breaks no scene claim and stands at the stored assignment. Plausibility `variant`, verdict `concept`. It breaks two invariants: in every input the background outnumbers the line color, and every input leaves room for another outline.
    - `background=SharedColor`, `background=VanishedColor`: on one input with `ex_out` empty, each gives every color of the input, the line color included. At the line color, the 0 cells form no nested outlines. Fails Fit at train0.
    - `background=RarestColor`: gives the line color, at which the 0 cells form no nested outlines. Fails Fit at train0.
- `fill-color`
    - `concept`: stored, 5.
    - `fill_color=OutNewColor`, `fill_color=AnyOutNewColor`: each reads train outputs, so on one input with `ex_out` empty it gives no value and the model is undefined on every input. Fails Fit at train0.
- `growth-direction` & `step-granularity`, `growth-direction` & `step-source`, `growth-direction` & `stop-rule`, `growth-direction` & `line-color`, `growth-direction` & `background`, `growth-direction` & `fill-color`, `step-granularity` & `step-source`, `step-granularity` & `stop-rule`, `step-granularity` & `line-color`, `step-granularity` & `background`, `step-granularity` & `fill-color`, `step-source` & `stop-rule`, `step-source` & `line-color`, `step-source` & `background`, `step-source` & `fill-color`, `stop-rule` & `line-color`, `stop-rule` & `background`, `stop-rule` & `fill-color`, `line-color` & `background`, `line-color` & `fill-color`, `background` & `fill-color`: the two branches' changes applied together

## Open parameters
none

## Not formed
- Growing gaps between consecutive outlines: train0's three outlines have two equal gaps of 2. A gap increment would be a parameter whose value here is 0, and no reader of the concept takes another value.
- Filling only the cells between outlines, or only the cells inside the outermost outline: train1 paints col 0 and row 9 with 5, and these lie outside its outermost outline. The test's col 9 is the same.
- Recoloring the input's outlines: every train output keeps them in the line color.
- One connected figure, such as a spiral, in place of separate outlines: every input's outlines are separate 4-components, and no pair joins them.

## Tickets filed
- none
