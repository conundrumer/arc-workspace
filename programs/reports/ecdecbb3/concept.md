# ecdecbb3

## Concept
- Each dot fires a beam straight at the nearest wall on each side of it across the walls; where a beam hits a wall it stops, and the hit point gets a little 3×3 bracket of wall color with the dot's color in the middle.

## Scene
- `walls`: one or more full-length straight lines of `line_color`, all on one axis, which differs between pairs, crossing a field of `background`.
- `dots`: single cells of `mark_color`, each off every wall and at least 3 cells from it, with a wall on at least one side of it across the wall axis.

## Rules
- `keep-input`: every cell the rules below do not paint keeps its input color.
- `beam`: from each dot, toward each of the two directions across the wall axis that has a wall, the cells from the dot up to the nearest wall in that direction take `mark_color`; a beam does not pass that wall.
- `hit-cell`: the wall cell a beam hits takes `mark_color`.
- `bracket`: the cells within `ring_radius` (Chebyshev) of the hit cell, other than the hit cell itself, take `line_color`, over the beam.

## Parameters
- `line_color`: 8
    - the color of the walls and of the bracket
- `mark_color`: 2
    - the color of the dots, the beams, and the hit cells
- `ring_radius`: 1
    - the half-width of the bracket square around the hit cell

## Scene parameters
- `background`: 0
