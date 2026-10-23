# e7b06bea

## Concept
- The concept case fits every pair (train0–train4, test0). The probe `work/task/e7b06bea/probe.py` reproduces each output.
- No witness has the verdict `other`.
- The generator applies the rule as `folded-line` states it: the runs of the stripe colors are as long as the bar, and the first run starts at the edge where the bar starts. No approximation is needed.
- The witnesses against the concept are in `programs/reports/e7b06bea/witnesses.json`, and each breaks a scene claim of the concept case.

## Choice points
- `start-edge`
    - `concept`: `start_edge` is stored (top).
    - `$DerivedStart`: replaces `corner-bar` and the start edge of `folded-line`. The start edge is derived as the edge perpendicular to the stripe edge that the bar touches. The model is undefined where the bar touches both or neither of those edges. It fits every pair. Witness `bar-at-bottom`, at the stored assignment, breaks `corner-bar`: the bar starts at the bottom-left corner. Plausibility `variant`, verdict `$DerivedStart`. The invariant it breaks: in every input, the bar starts at row 0.
- `run-phase`
    - `concept`: the runs are counted from the start edge.
    - `$BarPhase`: replaces the phase of `folded-line`. The first run covers the bar's first cell and runs on from there, and the cells before the bar take the cycle backward. It is undefined nowhere beyond the concept. It fits every pair. Witness `bar-off-corner`, at the stored assignment, breaks `corner-bar`: the bar covers rows 1–2. Plausibility `borderline`, verdict `$BarPhase`. The invariant it breaks: in every input, the bar starts at row 0.
- `stripe-edge`
    - `concept`: `stripe_edge` is stored (right).
    - `$DerivedStripeEdge`: replaces the edge of `edge-stripes`. The stripe edge is derived as the one edge whose line is a full-length line of one non-background color. The model is undefined where no edge, or more than one edge, has such a line. It fits every pair. Witness `stripes-at-left`, at the stored assignment, breaks `edge-stripes`: the stripes fill up to the left edge, and the concept is undefined there. Plausibility `variant`, verdict `$DerivedStripeEdge`. The invariant it breaks: in every input, the stripes are at the right edge.
- `stripe-unit`
    - `concept`: each line of the stripe block is one stripe, and it gives one run per cycle.
    - `$BandStripes`: replaces the stripe unit of `folded-line`. Each maximal block of adjacent lines of one color is one stripe. It is undefined nowhere beyond the concept. It fits every pair. Witness `repeated-stripe-color`, at the stored assignment, breaks `edge-stripes`: two adjacent stripes are color 4. Plausibility `borderline`, verdict `$BandStripes`. The invariant it breaks: in every input, the stripe colors are different from each other.
- `background`
    - `concept`: `background` is stored (0).
    - `background=DominantColor`: the background is derived as the commonest color of the input. The model is undefined where two colors tie for the highest count. It fits every pair. Witness `background=DominantColor`, at the stored assignment, breaks `background-field`: the cells outside the bar and the stripes are 7, and the concept is undefined there. Plausibility `variant`, verdict `background=DominantColor`. The invariant it breaks: in every input, the background is 0.
    - `background=SharedColor`: fails Fit at train0. On the train0 input alone, it gives each of 0, 1, 3 and 5.
- `run-length`
    - `concept`: the run length is the length of the bar.
    - `$StoredRunLength`: a stored run length. It fails Fit at train1: train0 needs 1 and train1 needs 3.
    - `$StripeCountRun`: the run length is the number of stripes. It fails Fit at train0: train0 has 2 stripes and runs of 1.
- `color-order`
    - `concept`: the cycle starts at the stripe nearest to the folded line.
    - `$EdgeFirstOrder`: the cycle starts at the stripe at the stripe edge. It fails Fit at train0: it gives `1 3 1 3 1` in place of `3 1 3 1 3`.
- `fold-line`
    - `concept`: the folded line is the line next to the stripe block on the bar side.
    - `$FoldOnFirstStripe`: the folded line is the line of the stripe nearest to the bar. It fails Fit at train0: it puts the line at col 3, and the output has it at col 2.
- `start-edge` & `stripe-edge`, `start-edge` & `stripe-unit`, `start-edge` & `background`, `run-phase` & `stripe-edge`, `run-phase` & `stripe-unit`, `run-phase` & `background`, `stripe-edge` & `stripe-unit`, `stripe-edge` & `background`, `stripe-unit` & `background`, and each pair that holds `run-length`, `color-order` or `fold-line`: the two branches' changes applied together
- `start-edge` & `run-phase`: the model of `$DerivedStart` alone. Where `$DerivedStart` is defined, the bar starts at the derived start edge, so the phase that `$BarPhase` reads from the bar is the phase from that edge. The `run-phase` property therefore exists only with the concept branch of `start-edge`, which the concept claims take, and the point stands at the concept.

## Open parameters
- none

## Not formed
- The folded line at a fixed column, or at a fixed distance from the bar: the pairs separate it (train0 puts the line at col 2 and train1 at col 4, with the bar at col 0 in both).
- The runs counted from the bottom edge: this is the value bottom of `start_edge`, which the pairs separate. At that value the concept fails train1, where row 6 is 9 and rows 3–5 are 8.
- The bar removed in the output: the pairs separate it, because every output keeps the bar.
- `bar_color` as a parameter that the program reads: the program finds the bar as the non-background cells outside the stripe block, so no case reads the bar's color.

## Tickets filed
- none
