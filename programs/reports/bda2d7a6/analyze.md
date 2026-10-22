# bda2d7a6

## Concept
- The concept case fits every train and test pair at `step` 1 (probe: `work/task/bda2d7a6/probe.py`).
- No witness has the verdict `other`.
- The generator's rule is the concept file's `cycle-colors` as written: the distinct colors, ordered by the depth of the ring where each first appears, cycle one place inward. It has a relational form: ring depth (`Rim`), the dense rank of each color's least depth (`Ordinal`), and the successor on that rank (`IndexCycle`). It is not an approximation.
- Under the scene claims, `$EnclosingColor` gives the concept's output on every input. They part only where `color-cycle` is broken.
- On periodic rings of width 1, `$CountOrder` and `$RingShift` give the concept's output on every input. They part where the ring colors do not repeat with period `color-count`.

## Choice points
- `rule`: what the output takes from the input
    - `concept`: each cell is recolored by a cycle over the input's distinct colors (`cycle-colors`)
        - `predecessor`: which color each color takes
            - `concept`: the color one place before it in the outside-in order of first appearance, with the first wrapping to the last
            - `$CountOrder`: replaces `cycle-colors`'s order with the order of the colors by cell count, highest first. The model is undefined where two colors have the same count. Fits every pair. Witness `non-periodic-rings`: it breaks no scene claim, is `variant`, and its verdict is `concept`. It breaks this invariant of the inputs: the ring colors repeat with period `color-count`.
            - `$EnclosingColor`: replaces `cycle-colors` with this rule: each color takes the color of the ring just outside its outermost ring, and the outermost ring's color takes the last color to appear. Defined on every input of `nested-rings`. Fits every pair. Witness `repeat-before-new-color`: it breaks `color-cycle`, is `variant`, and its verdict is `concept`. It breaks this invariant of the inputs: the first `color-count` rings show distinct colors.
            - `$StoredMapping`: stores the color-to-color mapping as a lookup table in place of `cycle-colors`'s derived cycle. Fails Fit at train1: train0 maps 0 to 2, and train1 maps 0 to 6.
    - `$RingShift`: replaces `cycle-colors` with this rule: each ring takes the color of the ring just outside it, and the outermost ring takes the color of ring `color-count` − 1. Defined on every input of `nested-rings`. Fits every pair. Witness `non-periodic-rings` (also listed under `$CountOrder`): it breaks no scene claim, is `variant`, and its verdict is `concept`. It breaks this invariant of the inputs: the ring colors repeat with period `color-count`.
    - `$RingRoll`: replaces `cycle-colors` with this rule: each ring takes the color of the ring just outside it, and the outermost ring takes the innermost ring's color. Fails Fit at train2: it gives the rings 8 8 0 5 where the output has 5 8 0 5.
    - `$ReverseRings`: replaces `cycle-colors` with this rule (from the 85c4e7cd header): each ring takes the color of the ring as deep from the center as it is from the border. Fails Fit at train0: it gives the rings 0 2 3 where the output has 0 3 2.

## Open parameters
- none

## Not formed
- `step` at other values: `step` is a parameter of the concept case, not a claim, and the pairs fix it to 1. At `step` 2 each color takes the color one place after it, and train0 gives the rings 2 0 3 where its output has 0 3 2.
- Order of first appearance in row-major scan: on every input of `nested-rings` it gives the outside-in order. It parts from the concept only where a ring holds more than one color, and none of the allowed sources (pairs, solver headers, lib, proposers, probes, variant tasks) suggests that reading.
- A stored or derived `color-count` or `ring-width`: the rules read neither value, so neither one is a point.

## Tickets filed
- none
