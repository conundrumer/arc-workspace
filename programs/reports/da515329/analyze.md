# da515329

## Concept
- Fits every pair: the walk in `work/task/da515329/probe.py` (`concept`) gives train0, train1, train2 and test0 exactly.
- No witness with verdict `other` was found.
- The rule as the generator applies it: the four arms are drawn on as four clockwise spirals that wind around one another, with walls and lanes one cell wide, on a plane that the grid clips. `arms-grow` and `hug-the-spiral` build that drawing one cell per arm per step.

## Choice points
- `background`
    - `concept`: the stored background 0
    - `background=DominantColor`: replaces the stored field color of `one-plus` with the color that has the most cells in the input; no parameter; undefined on an input where two colors tie for the most cells. Fits every pair. Witness `background=DominantColor`: a field of 5 under the plus of train1. It breaks `one-plus` (the field is not 0), plausibility `variant`, verdict `background=DominantColor`, and it breaks the invariant "every input's field is 0".
    - `background=SharedColor`: gives 0 and 8 on each input, so no one field remains, and the model is undefined on every pair. Fails Fit at train0.
    - `background=RarestColor`: gives 8, and the 0 cells hold no plus. Fails Fit at train0.
- `wall color`
    - `concept`: the spiral takes the plus's color, read from the input
    - `wall_color=stored`: replaces the color in `clip` with a stored `wall_color` = 8; the plus is still read as the cells that are not `background`; no other parameter; undefined where the concept is undefined. Fits every pair. Witness `wall_color=stored`: the plus of train1 in 3. It breaks no scene claim, plausibility `variant`, verdict `concept`, and it breaks the invariant "every plus is 8".
- `spiral shape`
    - `concept`: the wall-following walk of `arms-grow` and `hug-the-spiral`
        - `growth order`
            - `concept`: all four arms take one cell each in one step, against the walls that stood before the step
            - `$TakeTurns`: replaces `arms-grow`: the arms move one at a time, each against the cells the others have just taken, starting from the arm `first_arm` = up and going on in `sense` order; undefined where the concept is undefined. Fits every pair. Witness `stray-cell-contest`: the plus of arm length 2 at (4,4) in an 8×8 grid with a stray 8 at (7,3). It breaks `one-plus` (a cell outside the plus), plausibility `foreign`, verdict `any`, and it breaks the invariant "every input holds the plus and nothing else".
            - `$OneArmAtATime`: replaces `arms-grow`: each arm grows to its end before the next arm starts. Fails Fit at train0.
        - `lane neighborhood`
            - `concept`: the lane test reads the five cells ahead of and beside the new cell, the diagonals ahead included
            - `$Lane4`: replaces `hug-the-spiral`: the lane test reads only the cell ahead and the two cells beside the new cell. Fails Fit at train0.
    - `$SquareRings`: replaces `hug-the-spiral`: each arm draws a plain square spiral from its tip, turning in `sense`, its k-th segment at distance L + 2k from the center, with L the arm length. Fails Fit at train0 (it fits train2 alone).
    - `$LengthTable`: replaces `arms-grow`, `hug-the-spiral` and `clip` with a lookup table from arm length to the drawing around the center. Fails Fit at test0 by Unseen key: the test arm length is 4, and the train lengths are 3, 1 and 2.
- `edge`
    - `concept`: the arms grow on an unbounded plane, and the grid clips the drawing
    - `$EndAtEdge`: replaces `arms-grow`: an arm ends where its next cell would leave the grid. Fails Fit at train0: train0 output (21,21) is 8, where a spiral comes back into the grid.
    - `$EdgeIsWall`: replaces `hug-the-spiral`: the cells past the frame count as wall in the lane test. Fails Fit at train0.
- `background` & `wall color`, `background` & `spiral shape`, `background` & `edge`, `background` & `growth order`, `background` & `lane neighborhood`, `wall color` & `spiral shape`, `wall color` & `edge`, `wall color` & `growth order`, `wall color` & `lane neighborhood`, `spiral shape` & `edge`, `growth order` & `edge`, `lane neighborhood` & `edge`, `growth order` & `lane neighborhood`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- a derivation of `sense`: the plus is symmetric under every reflection, so no fact of an input gives a sense, and the pairs fix it at clockwise.
- a derivation of `corridor_width`: no fact of an input gives a width; the arm length runs from 1 to 4 across the inputs, and the lane stays 1 wide.

## Tickets filed
- none
