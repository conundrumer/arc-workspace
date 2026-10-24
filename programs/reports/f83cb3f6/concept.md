# f83cb3f6

## Concept
- A straight wall with holes crosses the grid, and loose dots on each side are pulled straight onto it: each dot sticks to the face of the wall on its own side, dots on one line pile into one, and a dot whose line meets a hole in the wall falls through and is gone.

## Scene
- `one-wall`: one straight line of `wall_color` cells crosses the grid from edge to edge along one axis, at neither border, so both sides have cells; some cells of the line may be missing, and those are its holes.
- `dots`: every other non-`background` cell is a single dot of one color, other than `wall_color`, the same for all dots of an input; dots lie on both sides of the wall.

## Rules
- `keep-wall`: the wall cells stay as they are.
- `pull-to-wall`: for each line perpendicular to the wall, and each side of the wall, where that line has a wall cell and at least one dot on that side, the cell next to the wall cell on that side takes the color of the dot on that line and side nearest the wall.
- `hole-drops`: dots on a line that meets a hole in the wall leave no mark.
- `clear-rest`: every other cell is `background`.

## Parameters
- `wall_color`: 8
- `background`: 0

## Scene parameters
none
