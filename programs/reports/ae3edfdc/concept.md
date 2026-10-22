# ae3edfdc

## Concept
- Each center cell pulls the cells of its partner color that lie in its row or column straight in to touch it, one on each side, like planets falling onto a sun.

## Scene
- `single-cells`: on a `background` field, every non-background cell stands alone, with no other non-background cell next to it.
- `one-center-per-color`: each center color of `pair` has exactly one cell.
- `satellites-in-line`: each cell of a satellite color of `pair` lies in the row or the column of the center its color is paired with.
- `one-per-side`: each center has at most one satellite on each of its four sides.

## Rules
- `pull-in`: each satellite moves along its line to the cell next to its center on the satellite's side.
- `centers-stay`: each center stays where it is.
- `rest-background`: every other cell of the output is `background`.

## Parameters
- `background`: 0
- `pair`: 2 → 3, 1 → 7
    - the center color, mapped to the color of its satellites

## Scene parameters
- none
