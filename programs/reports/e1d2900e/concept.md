# e1d2900e

## Concept
- Each dot that lies in line with a square slides straight toward the nearest such square until it touches it; a dot in line with no square stays where it is.

## Scene
- `background`: a field of `background_color`.
- `squares`: solid squares of `square_color`, each `square_size` by `square_size`, apart from one another.
- `dots`: single cells of `dot_color`, apart from the squares and from one another.

## Rules
- `in-line`: a dot is in line with a square when the dot's row crosses the square's rows, or the dot's column crosses the square's columns.
- `nearest-square`: of the squares a dot is in line with, the dot takes the one with the fewest cells between the dot and the square along that line.
- `slide-to-touch`: the dot moves along that line to the cell next to the square's facing side, and its old cell becomes background.
- `stay`: a dot in line with no square keeps its cell.
- `squares-kept`: the squares keep their cells.

## Parameters
- `background_color`: `0`
- `square_color`: `2`
- `dot_color`: `1`

## Scene parameters
- `square_size`: `2`
