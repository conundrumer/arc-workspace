# f8f52ecc

## Concept
- Dots of one color mark the ends and bends of a hidden route; draw each color's route with straight horizontal and vertical lines that join all its dots by the shortest, straightest way that never crosses a `wall_color` wall.

## Scene
- `background`: a field of `background`.
- `walls`: straight segments of `wall_color`, which no route crosses.
- `dots`: scattered cells of other colors; some colors have one cell, and the cells of each color with several can all be joined by one 4-connected route over `background` cells that avoids the walls.

## Rules
- `join-dots`: for each color other than `background` and `wall_color` that has two or more cells, the output paints in that color the cells of the 4-connected route through all of its cells that adds the fewest cells, avoiding `wall_color` cells; among such routes, the one with the fewest turns.
- `keep-rest`: every other cell keeps its input color; a color with one cell, and `wall_color`, are left as they are.

## Parameters
- `background`: 1
    - the field color, the only color a route paints over
- `wall_color`: 8
    - the color whose cells block a route and are never joined

## Scene parameters
- none
