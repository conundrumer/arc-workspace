# e1d2900e

## Concept
- The concept fits every train pair and the test pair. Its rules have a relational form, and no rule is an approximation.
- The concept is undefined on an input where a dot has the same gap to two squares it lies in line with. No input in the evidence has such a dot. Witness `tie`: plausibility `ordinary`, verdict `any`.
- Where one dot lies on another dot's slide path to the same square side, the concept lands both dots on one cell, so the output loses a dot. Witness `dot-on-path`: plausibility `ordinary`, verdict `$PathStack`.
- No witness has the verdict `other`.

## Choice points
- `pulling-square`: which of the squares a dot lies in line with it slides to
    - `concept`: the square with the fewest cells between it and the dot; undefined where two squares tie
    - `$TieStay`: replaces `nearest-square`; a dot with a tie keeps its cell; defined on every input. Fits every pair. Witness `tie`, at the stored assignment, breaks no scene claim; plausibility `ordinary`, verdict `any`.
    - `$TieBoth`: replaces `nearest-square`; a dot with a tie is drawn beside each tied square; defined on every input. Fits every pair. Witness `tie`; plausibility `ordinary`, verdict `any`.
    - `$TieEither`: replaces `nearest-square`; a dot with a tie gives one output grid per tied square; defined on every input. Fits every pair. Witness `tie`; plausibility `ordinary`, verdict `any`.
    - `$AllSquares`: replaces `nearest-square`; a dot is drawn beside every square it lies in line with. Fails Fit at train0: the dot at train0 input (16,20) also lands at (16,12), which is `0` in the output.
- `dot-on-path`: what a dot does when another dot lies between it and the square it slides to
    - `concept`: the dot passes the other dot, and both land on the cell beside the square
    - `$PathBlocked`: adds to `nearest-square`; a slide whose path holds another dot is ruled out, the dot takes the nearest slide left, and a dot with none keeps its cell. Fits every pair. Witness `dot-on-path`, at the stored assignment, breaks no scene claim; plausibility `ordinary`, verdict `$PathStack`.
    - `$PathStack`: replaces `slide-to-touch`; the dots that slide to one side of a square along one line pack against it, nearest first. Fits every pair. Witness `dot-on-path`; plausibility `ordinary`, verdict `$PathStack`.
    - `$StopAtDot`: replaces `slide-to-touch`; a dot stops against the first dot on its path, and the slide length counts to that stop. Fails Fit at train0: the dot at train0 input (15,18) stops at (10,18) against the dot at (9,18), in place of (15,12).
- `slide-lines`: the lines a dot slides along
    - `concept`: a row or a column that crosses the square
    - `$DiagSlide`: adds diagonal slides that end on a cell touching a square at a corner alone. Fails Fit at test0: the dot at test0 input (20,28) slides to (24,24), and the test output keeps it at (20,28).
- `stray-dot`: what happens to a dot in line with no square
    - `concept`: it keeps its cell (`stay`)
    - `$DropStray`: replaces `stay`; the dot clears to background. Fails Fit at train0: train0 output keeps the dot at (10,26).
- `square-roles`: how the program tells dots from squares
    - `concept`: by the stored `dot_color` and `square_color`
        - `dot_color`
            - `concept`: stored
            - `dot_color=RarestColor`: derives `dot_color` as the rarest color of the input. Fails Fit at train1: train1 input has 8 cells of `2` and 11 of `1`, so the derived dot color is `2`.
        - `square_color`
            - `concept`: stored
            - `square_color=RarestColor`: derives `square_color` as the rarest color of the input. Fails Fit at train0: train0 input has 14 cells of `1` and 16 of `2`, so the derived square color is `1`.
    - `$RolesByShape`: replaces the scene claims `squares` and `dots` as the program reads them; every single-cell component of a non-background color is a dot, every larger component is a square, and a dot keeps its own color; reads no `dot_color` or `square_color`. Fits every pair. Witness `extra-color-dot`, at the stored assignment, breaks no scene claim; plausibility `borderline`, verdict `any`; it breaks the invariant that every input holds only the colors `0`, `1` and `2`.
- `square-shape`: which components of `square_color` pull dots
    - `concept`: every component
    - `$SquareSizeChecked`: adds to `in-line`; only a solid `square_size` by `square_size` component pulls dots, and the program reads `square_size`. Fits every pair. Witness `large-block`, at the stored assignment, breaks the scene claim `squares`; plausibility `borderline`, verdict `concept`; it breaks the invariant that every component of `2` is a 2 by 2 square.
- `background_color`
    - `concept`: stored
    - `background_color=DominantColor`: derives `background_color` as the commonest color of the input; undefined where two colors tie for commonest. Fits every pair. Witness `background_color=DominantColor` breaks no scene claim; plausibility `borderline`, verdict `concept`; it breaks the invariant that `0` is the commonest color of every input.
- `pulling-square` & `dot-on-path`, `pulling-square` & `slide-lines`, `pulling-square` & `stray-dot`, `pulling-square` & `square-roles`, `pulling-square` & `square-shape`, `pulling-square` & `background_color`, `dot-on-path` & `slide-lines`, `dot-on-path` & `stray-dot`, `dot-on-path` & `square-roles`, `dot-on-path` & `square-shape`, `dot-on-path` & `background_color`, `slide-lines` & `stray-dot`, `slide-lines` & `square-roles`, `slide-lines` & `square-shape`, `slide-lines` & `background_color`, `stray-dot` & `square-roles`, `stray-dot` & `square-shape`, `stray-dot` & `background_color`, `square-roles` & `square-shape`, `square-roles` & `background_color`, `square-shape` & `background_color`, `dot_color` & `pulling-square`, `dot_color` & `dot-on-path`, `dot_color` & `slide-lines`, `dot_color` & `stray-dot`, `dot_color` & `square-shape`, `dot_color` & `background_color`, `square_color` & `pulling-square`, `square_color` & `dot-on-path`, `square_color` & `slide-lines`, `square_color` & `stray-dot`, `square_color` & `square-shape`, `square_color` & `background_color`, `dot_color` & `square_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Nearest square by the distance from the dot to the square's center: the center is a mean of cell positions, so the claim has no relational form.
- Nearest square by the taxicab distance from the dot to the square's nearest cell: along a line that crosses the square, that distance is the gap plus one, so the model is equivalent to the concept.
- Nearest square by the distance to the square's far side: no reader of the concept measures a slide past the square it reaches.
- The other proposers of a color for `background_color`, `dot_color` and `square_color`: on one input alone, each one gives no value (the proposers that read `ex_out`), more than one value (`SharedColor`), or a value other than the stored one, so no further derivation gives the stored colors on every pair.

## Tickets filed
- none
