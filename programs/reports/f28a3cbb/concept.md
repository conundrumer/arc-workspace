# f28a3cbb

## Concept
- Two solid squares sit in opposite corners, each with stray cells of its color scattered about; every stray cell is pulled to its own square and sticks to the square's side, moving diagonally toward the square while it lies beside neither of the square's row and column bands, then straight.

## Scene
- `background`: every cell that is in no square and no stray holds the color `background`.
- `two-corner-squares`: two solid squares of side `square_size`, each of its own color, sit in the two opposite corners `square_corners` of a grid of size `grid_size`; each is the largest solid square of its color.
- `strays-of-square-colors`: every other non-background cell is a stray: a cell of one of the two squares' colors, outside both squares and not touching its own square's side; strays may touch one another.

## Rules
- `squares-stay`: each square stays where it is.
- `stray-vacates`: each stray's cell becomes `background`.
- `stray-in-band-attaches`: a stray in a row band or a column band of its square lands in the cell on that row or column that touches the square's side facing it; strays that land on one cell make one cell.
- `stray-off-band-diagonal`: a stray in neither band steps diagonally toward its square until it enters a band, then lands as a stray in that band does; if it reaches the cell touching the square's corner first, it stays there.

## Parameters
- `background`: 6

## Scene parameters
- `square_size`: 3
- `square_corners`: top-left and bottom-right
- `grid_size`: 9×9
