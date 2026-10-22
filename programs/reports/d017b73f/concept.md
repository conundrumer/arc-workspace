# d017b73f

## Concept
- A strip holds short path pieces separated by empty columns; drop the empty columns and slide each piece up or down so that it continues the previous piece's path, joining all pieces into one unbroken line.

## Scene
- `strip-of-pieces`: the input is a strip `strip-height` rows high on a `background` field; it holds pieces, each a 4-connected set of cells of one color, and each column holds cells of at most one piece.
- `pieces-in-column-bands`: the pieces take disjoint column bands in order along `chain-dir`, and every column between two bands is empty.
- `first-piece-at-edge`: the first piece starts at the strip's edge opposite `chain-dir`, with no empty column before it.
- `piece-is-path`: each piece is a simple path with one end in its first column and the other end in its last column (along `chain-dir`); its first column holds only its start cell.
- `chain-fits`: each piece, once moved, stays inside the strip's rows.

## Rules
- `drop-empty-columns`: the output has the input's height and the pieces' columns alone, in order, with no empty column between them.
- `first-piece-stays`: the first piece keeps its rows.
- `continue-path`: each later piece moves across the strip so that its start cell lies in the row of the previous piece's end cell (the cell of the previous piece's last column that has at most one neighbor in its piece), right next to that end cell.
- `colors-kept`: each piece keeps its color, and every other cell is `background`.

## Parameters
- `background`: 0
- `chain-dir`: right
    - the direction along which the pieces chain, from the first piece to the last

## Scene parameters
- `strip-height`: 3
