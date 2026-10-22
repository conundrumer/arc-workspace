# b745798f

## Concept
- Fits every pair: `work/task/b745798f/probe.py` gives each train output and the test output.
- Each claim has a relational form: one-color 4-adjacent components (`Components` keyed by color), the 2×2 box corner a three-cell piece leaves open, and per edge the cells nearer one end than the other.
- Witnesses with verdict `other`: none.

## Choice points
- `piece-parse`: how the cells of one piece are gathered
    - `concept`: one-color sets, 4-adjacent within the color
    - `$Pieces8Adjacent`: replaces `four-l-pieces` with one-color sets joined by 8-adjacency, so same-color pieces that touch at a corner are one set and are not placed; no parameter; defined wherever the concept is. Fits every pair. Witness `diagonal-same-color` (two color-3 pieces touch at a corner): breaks no scene claim; stored assignment; `ordinary`; verdict `concept`.
    - `$PiecesAnyColor`: replaces `four-l-pieces` with 4-adjacent sets of any non-background colors, a set of more than one color is not placed; no parameter. Fails Fit at train2 (the 2, 7 and 4 pieces touch and form one set).
    - `$PieceByColorClass`: replaces `four-l-pieces` with all cells of one color as one piece; no parameter. Fails Fit at train0 (the two 5 pieces form one six-cell set).
- `piece-shape`: which sets are pieces
    - `concept`: three cells that fill a 2×2 box less one cell
    - `$PieceAnyL`: replaces `four-l-pieces` with a set that is exactly two edges of its bounding box meeting at one corner, any arm length of 2 or more, that corner the bend; no parameter; defined wherever the concept is. Fits every pair. Witness `longer-arms` (the 2 piece of train0 with arms of three cells): breaks `four-l-pieces`; stored assignment; `variant`; verdict `$PieceAnyL`; breaks the invariant that every piece is three cells in a 2×2 box.
- `corner-choice`: which grid corner a piece goes to
    - `concept`: the corner its bend cell takes in its 2×2 box (`piece-to-corner`)
    - `$CornerByArrangement`: replaces `piece-to-corner` with the piece's place among the four pieces, the two with the topmost rows going to the top corners and the left one of each two to the left corner; no parameter; undefined where the input has other than four pieces. Fails Fit at train2 (the 0 piece is top-right of the four and goes bottom-left).
    - `$CornerByQuadrant`: replaces `piece-to-corner` with the grid quadrant that holds the center of the piece's box; no parameter. Fails Fit at train0 (the 1 piece sits in the top half and goes bottom-left).
- `arm-extent`: how far each arm runs along its edge
    - `concept`: the edge cells nearer the corner than the edge's other end (`arms-to-middle`)
    - `$ArmKeepsGap`: replaces `arms-to-middle` with (length - 1) // 2 cells per edge, so on an even edge two cells stay background between the arms; no parameter; defined wherever the concept is. Fits every pair. Witness `even-side` (a 10×10 grid of four pieces): breaks `square-odd-grid`; stored assignment; `borderline`; verdict `concept`; breaks the invariant that every input has an odd side.
- `background`
    - `concept`: stored, 8
    - `background=DominantColor`: derives `background` as the commonest color of the input; undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor` (train1 with its field recolored 1): breaks `background-field`; stored assignment; `variant`; verdict `background=DominantColor`; breaks the invariant that 8 fills every cell outside the pieces.
- `input-pieces`: what becomes of the input pieces' cells
    - `concept`: background (`rest-background`)
    - `$KeepPieces`: replaces `rest-background` with the input pieces kept in place under the drawn arms; no parameter; undefined where a kept piece and an arm of another color meet on one cell. Fails Fit at train0 (output (1,2) is 8 where the input piece of 2 stands).
- `piece-parse` & `piece-shape`, `piece-parse` & `corner-choice`, `piece-parse` & `arm-extent`, `piece-parse` & `background`, `piece-parse` & `input-pieces`, `piece-shape` & `corner-choice`, `piece-shape` & `arm-extent`, `piece-shape` & `background`, `piece-shape` & `input-pieces`, `corner-choice` & `arm-extent`, `corner-choice` & `background`, `corner-choice` & `input-pieces`, `arm-extent` & `background`, `arm-extent` & `input-pieces`, `background` & `input-pieces`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- A stored arm length: the arms take 5, 4 and 2 cells in train0, train1 and train2, so no one value fits.
- Pieces scaled up into the corners: the arm of 5 cells in train0 is no whole multiple of a piece's 2-cell arm.
- The border ring colored by quadrant: it gives the concept's output on every input, so its model is equivalent to the concept's.
- One arm length for both edges of a non-square grid: every grid is square, and no reading of the pairs picks the side such a length comes from.
- `background` derived by another proposer: `SharedColor` gives every color of a lone input, so `background` takes several values and the model is undefined on every pair; `ChangedColor`, `UnchangedColor` and the other proposers that read `ex_out` give no value on a lone input, so the model is undefined on every pair.

## Tickets filed
- none
