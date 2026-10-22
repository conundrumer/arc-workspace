# bd5af378

## Concept
- The concept case fits every train and test pair (`probe_witnesses.py` checks each one). It finds the L as the color that fills one edge row and one edge column, with every other cell one color, and it reads the corner, the L's color and the field color from that, so no orientation or color of the input is stored. It is undefined where no color fills an edge row and an edge column with the rest one color.
- It has no witness with verdict `other`.

## Choice points
- `l-identification`: how the program finds the L
    - `concept`: the color that fills one edge row and one edge column, with every other cell one color
    - `$LByMinority`: replaces `l-line` as the program reads it: the L is the rarer of the input's two colors, and its edge row and column give the corner. Undefined where the input does not hold exactly two colors, where the two counts tie, or where the rarer color does not fill an edge row and an edge column. It fits every pair. Where it is defined it gives the concept's output, and it is undefined where the L outnumbers the field, so the concept subsumes it and it fails Subsumption. Witness `tiny-grid` (3x3 input, the L at the bottom-right): it breaks no scene claim. Plausibility `variant`. It breaks the invariant that every input is at least 5 cells on each axis. Verdict `concept`.
- `l-thickness`: what the L keeps when it steps in
    - `concept`: one layer at distance `shift` from the corner's edges takes the L's color, and the diagonal cells at distance at most `shift` take `fill_color`
    - `$MoveWholeL`: replaces `l-steps-in` and `corner-diagonal`: the L's input cells translate `shift` cells along the diagonal inward, clipped to the grid, and the diagonal cells through the moved L's corner cells take `fill_color`. It reads the L's thickness from the input. Undefined where the concept is undefined. It fits every pair, and it gives the concept's output on every one-cell-thick L. Witness `thick-l` (8x8, an L two cells thick at the bottom-right) stands at the stored assignment. It breaks scene claim `l-line` (`l_width` = 1). Plausibility `variant`. It breaks the invariant that the L is one cell thick in every input. Verdict `$MoveWholeL`.
- `fill_color`: how the program gets the fill color
    - `concept`: stored, 8
    - `fill_color=OutNewColor`: derives it as a color in every train output and no input. On one input with `ex_out` empty it gives no value, so the branch is undefined on every input. It fails Fit at train0. `AnyOutNewColor` gives no value there either, and every input-only color proposer (`SharedColor`, `DominantColor`, `RarestColor`) gives an input color and not 8, so each of those fails Fit at train0 too.
- `corner`: how the program gets the L's corner
    - `concept`: derived from the L in each input
    - `corner=stored`: one stored corner. It fails Fit at train1 (bottom-left, where train0 is bottom-right).
- `l_color`: how the program gets the L's color
    - `concept`: derived from the L in each input
    - `l_color=stored`: one stored color. It fails Fit at train1 (3, where train0 is 7).
- `field_color`: how the program gets the field color
    - `concept`: derived as the color of every cell off the L
    - `field_color=stored`: one stored color. It fails Fit at train1 (6, where train0 is 9).
- `l-identification` & `l-thickness`, `l-identification` & `fill_color`, `l-identification` & `corner`, `l-identification` & `l_color`, `l-identification` & `field_color`, `l-thickness` & `fill_color`, `l-thickness` & `corner`, `l-thickness` & `l_color`, `l-thickness` & `field_color`, `fill_color` & `corner`, `fill_color` & `l_color`, `fill_color` & `field_color`, `corner` & `l_color`, `corner` & `field_color`, `l_color` & `field_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `shift` derived: no proposer derives a value of 1 from one input with `ex_out` empty, and the pairs fix `shift` at 1.
- The diagonal as the line from the L's corner to the opposite grid corner, in place of a 45-degree ray: train0 (5x6) separates the two, since its ray ends at (0,1) and not at (0,0), and that line has no relational form on a grid that is not square.
- Only the two L corners as `fill_color` on the diagonal, in place of every diagonal cell within `shift` of the corner: at `shift` 1 the two sets of cells are the same, and at other values of `shift` it states no output that a reader of the pairs could take.
- The L's cells and the field cells next to them swapping colors, in place of the L stepping inward: on every input it gives the concept's output, so it is the same model.

## Tickets filed
- none
