# d017b73f

## Concept
- The concept case fits every train pair and the test pair (`probe.py` runs it over each pair).
- Each rule has a relational form: the pieces, the path ends (cells with at most one neighbor in their piece), the running row shift and the closing of the empty columns are all relations over cells, columns and counts the task has.
- On a chain that leaves the strip, the concept keeps the input's height and drops the cells past it (witness `descending-chain`).
- The concept is undefined where a piece's first column has no single path start, or its last column no single path end (witnesses `hook-end-inside`, `background=DominantColor`).
- No witness has the verdict `other`.

## Choice points
- `piece`: what one piece is
    - `concept`: a maximal run of non-empty columns, read as one piece
    - `$PieceComponent`: replaces `pieces-in-column-bands` as the program reads it; a piece is a 4-connected component of non-background cells, and the pieces are ordered by their first column; undefined where two pieces share a column. Fits every pair. Witness `diagonal-step`: it breaks `strip-of-pieces` (the concept's middle piece is not 4-connected), plausibility `borderline`, verdict `$PieceComponent`; the invariant it breaks is that every piece is 4-connected and an empty column lies between every two pieces.
        - `adjacency`: which cells join one component
            - `concept`: 4-adjacency
            - `$Adjacency8`: 8-adjacency, so cells that touch at a corner join one piece. Fits every pair. Witness `diagonal-step`: it breaks `strip-of-pieces`, plausibility `borderline`, verdict `$PieceComponent`; the invariant it breaks is that each set of cells joined by 8-adjacency is also joined by 4-adjacency.
        - `component-color`: whether a component holds one color
            - `concept`: cells of any colors join one component
            - `$OneColor`: a piece is a 4-connected component of one color. Fits every pair. Witness `two-color-piece`: it breaks `strip-of-pieces` (a piece of one color) and `piece-is-path`, plausibility `borderline`, verdict `$OneColor`; the invariant it breaks is that cells of two colors never touch.
- `end-cell`: the cell of the previous piece that the next piece's start lies beside
    - `concept`: the cell of the previous piece's last column with at most one neighbor in its piece
    - `$EndFarthestRow`: replaces `continue-path`'s end cell with the cell of the last column farthest from the piece's start row; undefined on a tie. Fits every pair. Witness `u-shape`: it breaks no scene claim, plausibility `ordinary`, verdict `concept`.
    - `$EndPathEnd`: replaces `continue-path`'s end cell with the path end other than the start, wherever it lies; undefined where the piece has no single such cell. Fits every pair. Witness `hook-end-inside`: it breaks `piece-is-path`, plausibility `foreign`, verdict `$EndPathEnd`; the invariant it breaks is that each piece's path ends in its last column.
    - `$EndTop`: replaces `continue-path`'s end cell with the topmost cell of the last column. Fails Fit at train0.
    - `$EndBottom`: replaces `continue-path`'s end cell with the bottommost cell of the last column. Fails Fit at train0.
- `anchor`: which piece keeps its rows
    - `concept`: the first piece (`first-piece-stays`)
    - `$AnchorLast`: replaces `first-piece-stays`; the last piece keeps its rows, and each earlier piece moves so that its end lies beside the next piece's start. Fails Fit at train1.
- `overflow`: what the output does where a moved piece passes the strip's rows
    - `concept`: the output keeps the input's height, and the cells past it are dropped
    - `$GrowFrame`: replaces the height in `drop-empty-columns`; the output frame extends to every row the moved pieces reach. Fits every pair. Witness `descending-chain`: it breaks `chain-fits`, plausibility `borderline`, verdict `$GrowFrame`; the invariant it breaks is that every moved piece stays inside the strip's rows.
- `background`: where the background color comes from
    - `concept`: stored, 0
    - `background=DominantColor`: derived on each input as its commonest color; undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`: it breaks `strip-of-pieces` at the stored background 0 (the field is 5), plausibility `variant`, verdict `background=DominantColor`; the invariant it breaks is that every input's field is 0.
- `piece` & `end-cell`, `piece` & `anchor`, `piece` & `overflow`, `piece` & `background`, `end-cell` & `anchor`, `end-cell` & `overflow`, `end-cell` & `background`, `anchor` & `overflow`, `anchor` & `background`, `overflow` & `background`, `adjacency` & `component-color`, `adjacency` & `end-cell`, `adjacency` & `anchor`, `adjacency` & `overflow`, `adjacency` & `background`, `component-color` & `end-cell`, `component-color` & `anchor`, `component-color` & `overflow`, `component-color` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `chain-dir` derived from the input: no proposer derives a direction, and in train0, train1, train2 and the test a piece touches both side edges, so the edge a piece touches does not give the start side.
- The next piece placed at any row where it touches the previous piece: in train0, piece B touches piece A at row 0 and at row 1, so the reading gives no single output and has no model.
- Empty columns kept between the moved pieces: the join puts each start right next to the previous end, which leaves no room for a column between them, and every output's width is the pieces' column count.
- Pieces as color classes (all cells of one color as one unit): in train3, the two color-2 pieces move on their own, and one color-2 unit cannot be placed beside piece A's end and still reproduce that output.
- A rule that picks the start cell among several cells of a piece's first column: every piece's first column holds one cell in every input, and no reading of the pairs takes a start other than that cell.

## Tickets filed
- none
