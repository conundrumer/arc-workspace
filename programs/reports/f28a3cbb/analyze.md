# f28a3cbb

## Concept
- Fits every pair (train0, train1, test0; `work/task/f28a3cbb/probe.py`). Each claim has a relational form: the bands are same-row/same-column relations to the square's box, and the diagonal approach is a same-diagonal relation toward the corner cell. No witness has verdict `other`. The concept loses out to a branch in two places, both inputs the generator could easily produce: at `same-line-strays` the verdict is `$Stack`, and at `domino-along-motion` it is `$RigidPieces`. In both, the concept's rule that strays landing on one cell make one cell drops a cell. The evidence never has two strays of one color on one line on the same side of their square. Every off-band stray in the evidence sits at a gap of (1,2) from its square's corner, so nothing in the evidence tests how a stray on the corner diagonal lands. While refining the concept I changed how squares are identified, from largest connected piece to largest solid square, because of the `stray-touching-side` witness. The concept clears every cell whose color has no square.

## Choice points
- `stray-collision`
    - `concept`: strays that land on one cell make one cell
    - `$Stack`: replaces `stray-in-band-attaches`; strays on one line pile outward from the side cell, the nearest first; defined wherever the concept is. Fits every pair. Witness `same-line-strays`: breaks no scene claim, plausibility `ordinary`, verdict `$Stack`.
- `stray-unit`
    - `concept`: each stray cell moves on its own
    - `$RigidPieces`: replaces `stray-in-band-attaches` and `stray-off-band-diagonal`; each 4-connected piece of strays of one color moves as one rigid body, straight along the band it overlaps (diagonally while it overlaps neither band), until one of its cells touches the square's side or corner cell; undefined on a body that overlaps both bands. Fits every pair. Witness `domino-along-motion`: breaks no scene claim, plausibility `ordinary`, verdict `$RigidPieces` (`$Stack` gives the same output).
- `off-band-landing`
    - `concept`: diagonal steps toward the square until the stray enters a band, then it attaches; a stray that reaches the corner cell stays there
    - `$NearestSide`: replaces `stray-off-band-diagonal`; the stray lands on each edge-adjacent cell of its square nearest it by Euclidean distance, painting both when two tie; defined wherever the concept is. Fits every pair. Witness `corner-diagonal-stray`: breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$MinorAxisFirst`: replaces `stray-off-band-diagonal`; the stray steps straight along the axis on which it is nearer a band, then attaches; undefined on a stray on the square's corner diagonal. Fits every pair, and wherever it is defined it gives the concept's output, so it is subsumed by the concept case and fails Subsumption. It has no witness on which it is defined. `corner-diagonal-stray` shows it is undefined there.
    - `$MajorAxisFirst`: replaces `stray-off-band-diagonal`; steps straight along the axis on which it is farther from a band first; undefined on the corner diagonal. Fails Fit at train1: (3,4) lands at (3,2), not (2,3).
    - `$OffBandClears`: replaces `stray-off-band-diagonal`; a stray in neither band clears. Fails Fit at train1: (3,4) is cleared.
    - `$NearestSideTaxi`: replaces `stray-off-band-diagonal`; nearest edge-adjacent cell by taxicab distance, both painted on a tie. Fails Fit at train1: (5,4) ties and paints (5,6) as well as (6,5).
    - `$NearestSideKing`: replaces `stray-in-band-attaches` and `stray-off-band-diagonal`; nearest edge-adjacent cell by king-move distance, all painted on a tie. Fails Fit at train0: (0,7) ties at (0,3), (1,3) and (2,3).
    - `$NearestTouching8`: replaces `stray-off-band-diagonal`; nearest cell 8-adjacent to the square, corner cells included. Fails Fit at train1: (3,4) lands at (3,3).
- `stray-target`
    - `concept`: a stray goes to the square of its own color
    - `$NearestSquare`: replaces `stray-in-band-attaches` and `stray-off-band-diagonal`; a stray goes to the nearest square whatever its color. Fails Fit at train0: the 9 at (6,0) goes to the 4 square.
- `squareless-cells`
    - `concept`: a cell whose color has no square clears
    - `$SquarelessKept`: adds that such a cell stays where it is; defined wherever the concept is. Fits every pair. Witness `squareless-color`: breaks `strays-of-square-colors`, plausibility `variant`, verdict `any`; it breaks the input invariant that every non-background cell has a square's color.
- `background`
    - `concept`: `background` stored, 6
    - `background=DominantColor`: replaces the stored `background` with the input's commonest color; undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`, train0's input with 6 recolored to 0: breaks `background`, plausibility `variant`, verdict `background=DominantColor`; it breaks the input invariant that the background is 6.
    - `background=SharedColor`: replaces the stored `background` with every color the one input holds; undefined wherever an input holds more than one color. Fails Fit at train0.
    - `background=RarestColor`: replaces the stored `background` with the input's rarest color; undefined on a tie. Fails Fit at train0: 9 and 4 tie as rarest.
- `square-location`
    - `concept`: squares are found anywhere in the grid
    - `square_corners=stored`: replaces `two-corner-squares`' derived squares with the solid blocks grown from the stored corners top-left and bottom-right; undefined where a stored corner holds background. Fits every pair. Witness `square_corners=stored`: breaks `two-corner-squares`, plausibility `borderline`, verdict `concept`; it breaks the input invariant that the squares sit only in the top-left and bottom-right corners.
- `square-size`
    - `concept`: a square's side is read off the input
    - `square_size=stored`: replaces `two-corner-squares`' derived side with the stored side 3; undefined where a color has several 3×3 solid blocks. Fits every pair. Witness `square_size=stored`: breaks `two-corner-squares`, plausibility `variant`, verdict `concept`; it breaks the input invariant that the squares are 3×3.
- `square-shape`
    - `concept`: a color's square is its largest solid square of side at least 2
    - `$LargestPiece`: replaces `two-corner-squares`' identification with the color's largest connected piece, when that piece is a solid square; undefined where two pieces tie for largest. Fits every pair. Witness `stray-touching-side`: breaks `strays-of-square-colors`, plausibility `variant`, verdict `concept`; it breaks the input invariant that no stray touches its own square's side.
- `stray-collision` & `stray-unit`, `stray-collision` & `off-band-landing`, `stray-collision` & `stray-target`, `stray-collision` & `squareless-cells`, `stray-collision` & `background`, `stray-collision` & `square-location`, `stray-collision` & `square-size`, `stray-collision` & `square-shape`, `stray-unit` & `off-band-landing`, `stray-unit` & `stray-target`, `stray-unit` & `squareless-cells`, `stray-unit` & `background`, `stray-unit` & `square-location`, `stray-unit` & `square-size`, `stray-unit` & `square-shape`, `off-band-landing` & `stray-target`, `off-band-landing` & `squareless-cells`, `off-band-landing` & `background`, `off-band-landing` & `square-location`, `off-band-landing` & `square-size`, `off-band-landing` & `square-shape`, `stray-target` & `squareless-cells`, `stray-target` & `background`, `stray-target` & `square-location`, `stray-target` & `square-size`, `stray-target` & `square-shape`, `squareless-cells` & `background`, `squareless-cells` & `square-location`, `squareless-cells` & `square-size`, `squareless-cells` & `square-shape`, `background` & `square-location`, `background` & `square-size`, `background` & `square-shape`, `square-location` & `square-size`, `square-location` & `square-shape`, `square-size` & `square-shape`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Background derived by OutNewColor, AnyOutNewColor, VanishedColor, ChangedColor or UnchangedColor: each reads train outputs, and under `@derive` it reads one input and no output, so it gives no value on any input.
- Landing cells stored per stray position, as a lookup table: test0's strays, such as the 8s at (3,6)–(3,8), sit at positions no train pair has, so the table fails Fit (Unseen key).
- A stored `grid_size`: no clause of any model reads the grid's size, so storing it changes no model.
- Squares that move or change: every pair keeps both squares in place, and nothing in the evidence suggests otherwise.

## Tickets filed
- none
