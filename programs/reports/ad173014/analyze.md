# ad173014

## Concept
- Fits every pair (`probe.py` reproduces train0–2 and test0). The rule has a relational form: the boxes are the nodes of a cycle whose edges are the loop's segments, and the sense of the walk is read off the loop. There is no witness with verdict `other`.
- `sense` is not open. Train0 has three boxes, and counterclockwise gives a different output there.
- The concept is undefined on a loop with a gap (`broken-loop`) and on a box with no shape (`empty-box`). In both witnesses, the verdict goes to a branch.

## Choice points
- `color-source`: what a shape's new color comes from
    - `concept`: the shape in the next box along the loop
        - `what-moves`: what a box takes from the next box
            - `concept`: that box's shape color, painted onto its own shape
            - `$ShapesMove`: replaces `color-turn`; each box takes the whole shape of the next box, cells and color. Undefined where a shape does not fit the box it moves into. Fails Fit at train0, where the top box keeps its plus shape and takes only the color 3.
        - `cycle-order`: how the boxes are ordered into the cycle
            - `concept`: walk along the loop
            - `$BboxRingOrder`: replaces `color-turn`'s "along the loop"; boxes are ordered clockwise around the ring of the bounding box of the `line_color` cells. Undefined where a box has no cell on that ring. Fits every pair. Witness `broken-loop`: breaks scene claim `loop`; plausibility `borderline`; verdict `$BboxRingOrder`; breaks the invariant that every input's loop is closed. Its model is defined there and the concept's model is not.
            - `$LexCycle`: replaces `color-turn`'s "along the loop"; boxes are ordered by `LexOrder` from a stored corner and primary axis, and the cycle wraps from the last box to the first in a stored sense. Fails Fit at train1 under each of the 16 assignments (`probe.py`).
        - `step`: how far along the cycle the source box is
            - `concept`: the next box
            - `$StepCount`: replaces `color-turn`'s "next"; a stored count `step` of boxes along the cycle, stored as 1. Fits every pair. Witness `two-steps`: stands at `step` = 2; breaks no scene claim; plausibility `variant`; verdict `$StepCount`; it breaks no invariant of the inputs (train1's input), and only a variant task stores a step count of 2.
        - `empty-box`: what a box with no shape does in the cycle
            - `concept`: every box is a member, and the model is undefined where a box holds no shape
            - `$SkipEmptyBoxes`: replaces `one-shape-per-box`'s reading in `color-turn`; a box with no shape is not a member of the cycle, and it stays empty. Fits every pair. Witness `empty-box`: breaks scene claim `one-shape-per-box`; plausibility `borderline`; verdict `$SkipEmptyBoxes`; breaks the invariant that every box holds a shape.
            - `$EmptyBoxErases`: as above; a box with no shape hands on `background`, so the shape that takes from it is erased. Fits every pair. Witness `empty-box`: same scene claim, plausibility and invariant; verdict `$SkipEmptyBoxes`.
    - `$StoredColorMap`: replaces `color-turn`; each shape takes a stored color-to-color map's image of its own color. Fails Fit at train1: train0 maps 6 to 3 and train1 maps 6 to 7.
- `background`: how the program gets the background color
    - `concept`: stored, 0
    - `background=DominantColor`: the commonest color of the input. Undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`: breaks scene claim `loop` (its loop is not a rectangle); plausibility `foreign`; verdict `concept`; breaks the invariant that 0 is the commonest color of every input. Its model is defined there and gives the one 0 cell of the large box as that box's shape.
- `what-moves` & `cycle-order`, `what-moves` & `step`, `what-moves` & `empty-box`, `cycle-order` & `step`, `cycle-order` & `empty-box`, `step` & `empty-box`, `background` & `color-source`, `background` & `what-moves`, `background` & `cycle-order`, `background` & `step`, `background` & `empty-box`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Ordering the boxes by angle around a center (the loop's center or the boxes' centroid): the center is a number that counts nothing the task has, so the reading has no relational form. `$BboxRingOrder` is the relational reading of the same order.
- Counterclockwise `sense`: this is a value of the stored parameter and not a branch. Train0 separates it.
- Derivations of `background` other than `DominantColor`: on one input alone, `SharedColor` gives every color present, `RarestColor` gives a shape color, and the proposers that read `ex_out` give nothing. None gives 0 alone, so each fails Fit at train0.
- Derivations of `line_color` and `frame_color`: no proposer gives one color on one input.
- A box whose shape has two colors: neither the pairs nor the solver headers suggest what such a box hands on. The concept is undefined there, and no reading was formed.

## Tickets filed
- none
