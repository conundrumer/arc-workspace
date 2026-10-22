# b7955b3c

## Concept
- Fits every train and test pair (`probe.py`).
- The generator draws each rectangle whole, in a drawing order, and then the marks. Each mark cell shows what the generator drew last there before the marks. The concept's rule approximates each rectangle by the bounding box of its visible cells, and approximates the drawing order by the order the visible cells give (a rectangle whose visible cell lies in another's box is over it), closed transitively.
- Witness `order-hidden`: two rectangles overlap only at the mark's center, so no visible cell gives their order, and the concept is undefined there. It breaks no scene claim. It stands at the stored assignment. Plausibility `borderline`, verdict `other`. It breaks this invariant of the inputs: each two rectangles whose boxes overlap show their order at a visible cell.
- Witness `hidden-end`: the end of a one-row bar lies under a mark, so the bar's box stops short of the bar, and the concept fills the hidden end with the background. It breaks `visible-extent`. It stands at the stored assignment. Plausibility `borderline`, verdict `other`. It breaks this invariant of the inputs: each rectangle shows a cell on each of its four sides outside the marks.

## Choice points
- `mark-cells`
    - `concept`: every cell of color `mark_color` is a mark cell
    - `$PlusOccurrences`: replaces the mark set of `erase-marks`: the mark cells are only the cells of whole placements of `mark_shape` in `mark_color`, so `mark_shape` becomes a parameter (the plus). A mark-colored cell outside every placement stays and acts as a rectangle cell. Undefined where the concept is undefined. It fits every pair. Witness `clipped-plus`: it breaks `marks` and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: every mark is a whole plus inside the frame.
- `mark-color`
    - `concept`: `mark_color` stored
    - `mark_color=RarestColor`: fails Fit at train0, because 4 (10 cells) is rarer than 8 (25 cells).
    - `mark_color=SharedColor`, `mark_color=VanishedColor`: on one input with `ex_out` empty, these give every color of the input, so no rectangle is left. Fails Fit at train0.
    - `mark_color=ChangedColor`, `mark_color=UnchangedColor`: with `ex_out` empty, these give no value, so the model is undefined on every input. Fails Fit at train0.
    - `mark_color=DominantColor`: gives the background color. Fails Fit at train0.
- `restore-source`
    - `concept`: the rectangle stack (`layered-rectangles`, `erase-marks`)
        - `unit`
            - `concept`: all cells of one color are one rectangle
            - `$ComponentUnits`: replaces the one-rectangle-per-color part of `layered-rectangles`: each 4-connected component of one color is a rectangle with its own box. Fails Fit at train2, because the mark splits the 2 rectangle, and (4,5), (4,6) take 4 where the output has 2.
        - `layer-order`
            - `concept`: the order the visible cells give, closed transitively
            - `$SmallestOnTop`: replaces that order in `erase-marks`: of the boxes that cover a mark cell, the one with the smallest area shows. Fails Fit at train0, because (3,4) takes 4 where the output has 7.
            - `$DirectOrder`: the order the visible cells give, with no transitive closure. Undefined where two rectangles that cover a mark cell are ordered only through a third. It fits every pair. Where it is defined, it gives the concept case's output, so the concept case's model subsumes it and it fails Subsumption. Witness `order-chain`: it breaks no scene claim and stands at the stored assignment. Plausibility `borderline`, verdict `concept`. It breaks this invariant of the inputs: each two rectangles whose boxes overlap show their order at a visible cell.
        - `background`
            - `concept`: the background is the bottom layer, a color whose box is the frame
            - `$DominantBackground`: adds a claim: the commonest non-mark color is the background, lies under every rectangle and is not one of them, and fills a mark cell that no rectangle covers. Undefined where two colors tie for commonest. It fits every pair. Witness `big-rectangle`: it breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`. It breaks this invariant of the inputs: the background is the commonest color.
    - `$NeighborMode8`: replaces `erase-marks`: each mark cell takes the commonest color of its non-mark 8-neighbors, repeated inward until no mark cell is left. Undefined at a tie. Fails Fit at train0, which has a tie.
    - `$NeighborMode4`: the same with 4-neighbors. Fails Fit at train0, which has a tie.
    - `$BetweenCover`: replaces the rectangle box in `erase-marks`: a rectangle covers a mark cell when its visible cells lie on both sides of the cell in its row or column. Fails Fit at train0, because no visible 7 cell lies on both sides of (3,4) in row 3 or col 4, and the output has 7 there.
- `mark-cells` & `mark-color`, `mark-cells` & `restore-source`, `mark-color` & `restore-source`, `mark-cells` & `unit`, `mark-cells` & `layer-order`, `mark-cells` & `background`, `mark-color` & `unit`, `mark-color` & `layer-order`, `mark-color` & `background`, `unit` & `layer-order`, `unit` & `background`, `layer-order` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored layer order, or stored rectangle colors: the colors and their order differ from pair to pair, so no assignment fits.

## Tickets filed
- none
